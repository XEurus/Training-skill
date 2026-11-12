#!/usr/bin/env python3
"""Render an experiment registry as Mermaid/Markdown and Excalidraw maps."""
import argparse
import hashlib
import heapq
import html
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile
import time
import unicodedata
from urllib.parse import quote, urlsplit

STATUSES = {"planned", "running", "finished", "failed", "interrupted", "archived", "unknown"}
RESEARCH_RELATIONS = {"derived_from", "continues_from", "compares_to", "merges_from"}
DEPENDENCY_RELATIONS = {"uses_model", "uses_data", "produces"}
RELATIONS = RESEARCH_RELATIONS | DEPENDENCY_RELATIONS
RELATION_LABELS = {
    "zh": {"derived_from": "研究派生", "continues_from": "继续研究", "compares_to": "对照比较",
           "merges_from": "研究合并", "uses_model": "使用模型", "uses_data": "使用数据", "produces": "产出"},
    "en": {"derived_from": "Research derivation", "continues_from": "Continues research",
           "compares_to": "Compares", "merges_from": "Merges research", "uses_model": "Uses model",
           "uses_data": "Uses data", "produces": "Produces"},
}
MANAGED_BY = "mlflow-experiment-journal"
NODE_WIDTH = 460
NODE_GAP_X = 220
NODE_GAP_Y = 72
LAYOUT_LEFT = 80
LAYOUT_TOP = 190
STATUS_COLORS = {
    "planned": ("#fff9db", "#e67700"),
    "running": ("#e7f5ff", "#1971c2"),
    "finished": ("#e6fcf5", "#087f5b"),
    "failed": ("#fff0f0", "#c92a2a"),
    "interrupted": ("#fff0f0", "#c92a2a"),
    "archived": ("#f1f3f5", "#495057"),
    "unknown": ("#f1f3f5", "#495057"),
}
LABELS = {
    "zh": ["实验路径图", "更新", "研究路线", "代码与分支", "训练 runs", "文件与产物路径", "尚无实验节点。", "主题", "状态", "主要改动", "已确定发现 / 决定", "节点", "版本", "仓库 / 主机", "分支 / commit", "未提交修改", "worktree", "代码快照 / patch", "观察时间", "笔记", "用途", "位置", "存储类型"],
    "en": ["Experiment path map", "Updated", "Research routes", "Code and branches", "Training runs", "Files and artifacts", "No experiment nodes yet.", "Study", "Status", "Main changes", "Agreed findings / decision", "Node", "Revision", "Repository / host", "Branch / commit", "Uncommitted changes", "Worktree", "Code snapshot / patch", "Observed at", "Notes", "Role", "Location", "Storage"],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def string(value, name, nullable=False):
    require((nullable and value is None) or isinstance(value, str), f"{name} must be a string" + (" or null" if nullable else ""))


def objects(value, name):
    require(isinstance(value, list) and all(isinstance(item, dict) for item in value), f"{name} must be a list of objects")


def _validate_overview(value, name, kind):
    """Optional compact-view metadata stays separate from detailed-view hints."""
    require(isinstance(value, dict), f"{name} must be an object")
    strings = {"registry": ("title",), "node": ("title", "group", "loss", "result", "detail_path"),
               "edge": ("label",)}[kind]
    for key in strings:
        if key in value:
            string(value[key], f"{name}.{key}")
    for key in {"registry": ("context",), "node": ("config",), "edge": ()}[kind]:
        if key in value:
            require(isinstance(value[key], list) and all(isinstance(item, str) for item in value[key]),
                    f"{name}.{key} must be a string list")
    for key in {"registry": (), "node": ("include",), "edge": ("show",)}[kind]:
        if key in value:
            require(type(value[key]) is bool, f"{name}.{key} must be boolean")
    if kind == "node" and "order" in value:
        require(type(value["order"]) in (int, float) and math.isfinite(value["order"]),
                f"{name}.order must be finite numeric data")
    if kind == "registry" and "max_columns" in value:
        require(type(value["max_columns"]) is int and 1 <= value["max_columns"] <= 3,
                f"{name}.max_columns must be an integer from 1 to 3")


def validate(data):
    require(isinstance(data, dict) and data.get("schema_version") == 1, "Expected schema_version 1")
    string(data.get("project"), "project")
    string(data.get("updated_at"), "updated_at", nullable=True)
    _validate_overview(data.get("overview", {}), "overview", "registry")
    nodes, edges = data.get("nodes"), data.get("edges")
    objects(nodes, "nodes")
    objects(edges, "edges")
    ids, seen_runs = set(), set()
    for node in nodes:
        nid = node.get("id")
        string(nid, "node.id")
        require(bool(nid) and nid not in ids, f"Duplicate or empty node id: {nid}")
        ids.add(nid)
        for key in ("title", "study"):
            string(node.get(key), f"{nid}.{key}")
        require(isinstance(node.get("execution_status"), str) and node["execution_status"] in STATUSES, f"Invalid execution_status for {nid}")
        for key in ("changes", "findings", "results", "evidence"):
            value = node.get(key, [])
            require(isinstance(value, list) and all(isinstance(x, str) for x in value), f"{nid}.{key} must be a string list")
        for key in ("decision", "note_path", "summary", "question"):
            string(node.get(key), f"{nid}.{key}", nullable=True)
        _validate_overview(node.get("overview", {}), f"{nid}.overview", "node")
        display = node.get("display", {})
        require(isinstance(display, dict), f"{nid}.display must be an object")
        for key in ("group", "primary_path"):
            string(display.get(key), f"{nid}.display.{key}", nullable=True)
        for key in ("order", "x", "y", "width"):
            value = display.get(key)
            require(value is None or (type(value) in (int, float) and math.isfinite(value)),
                    f"{nid}.display.{key} must be finite numeric data")
        require(display.get("width") is None or display["width"] >= 180, f"{nid}.display.width must be at least 180")
        require((display.get("x") is None) == (display.get("y") is None), f"{nid}.display.x and y must be supplied together")
        for key in ("revisions", "runs", "paths", "executions"):
            objects(node.get(key, []), f"{nid}.{key}")
        revision_ids = set()
        for rev in node.get("revisions", []):
            rid = rev.get("id")
            string(rid, f"{nid}.revision.id")
            require(bool(rid) and rid not in revision_ids, f"Duplicate or empty revision id in {nid}: {rid}")
            revision_ids.add(rid)
            for key in ("repo", "branch", "commit", "worktree", "host", "observed_at", "code_snapshot", "patch_path"):
                string(rev.get(key), f"{nid}.{rid}.{key}", nullable=True)
            require(rev.get("dirty") is None or isinstance(rev["dirty"], bool), f"{nid}.{rid}.dirty must be boolean or null")
        for run in node.get("runs", []):
            for key in ("run_id", "tracking_uri", "revision_id"):
                string(run.get(key), f"{nid}.run.{key}")
                require(bool(run[key]), f"{nid}.run.{key} must be nonempty")
            for key in ("experiment_id", "url", "status"):
                string(run.get(key), f"{nid}.run.{key}", nullable=True)
            require(run["revision_id"] in revision_ids, f"Run {run['run_id']} references missing revision")
            identity = (run["tracking_uri"], run["run_id"])
            require(identity not in seen_runs, f"Duplicate run identity: {identity}")
            seen_runs.add(identity)
        execution_ids = set()
        for execution in node.get("executions", []):
            eid = execution.get("id")
            string(eid, f"{nid}.execution.id")
            require(bool(eid) and eid not in execution_ids, f"Duplicate or empty execution id in {nid}: {eid}")
            execution_ids.add(eid)
            for key in ("backend", "status", "observed_at", "directory", "revision_id", "host"):
                string(execution.get(key), f"{nid}.execution.{key}", nullable=True)
            require(execution.get("revision_id") is None or execution["revision_id"] in revision_ids,
                    f"Execution {eid} references missing revision")
        for path in node.get("paths", []):
            for key in ("role", "location"):
                string(path.get(key), f"{nid}.path.{key}")
            string(path.get("host"), f"{nid}.path.host", nullable=True)
            require(path.get("storage") in ("external", "mlflow-artifact"), f"Invalid path storage in {nid}")
    for edge in edges:
        _validate_overview(edge.get("overview", {}), "edge.overview", "edge")
        for key in ("from", "to", "relation"):
            string(edge.get(key), f"edge.{key}")
        require(edge["from"] in ids and edge["to"] in ids, "Edge references missing node")
        require(edge["from"] != edge["to"], "Self edges are not supported")
        require(edge["relation"] in RELATIONS, "Unknown edge relation")
        string(edge.get("label"), "edge.label", nullable=True)
        evidence = edge.get("evidence", [])
        require(isinstance(evidence, list) and all(isinstance(item, str) for item in evidence), "edge.evidence must be a string list")


def cell(value):
    if value is None or value == "":
        return "—"
    text = html.escape(str(value), quote=True).replace("|", "&#124;")
    for char in ("`", "[", "]", "*", "_"):
        text = text.replace(char, "\\" + char)
    return text.replace("\r", "").replace("\n", "<br>")


def location(value, label=None):
    if not value:
        return "—"
    display = cell(label or value)
    # Remote host paths are shown alongside their host, not rewritten into local paths.
    if urlsplit(value).scheme in ("http", "https") and not any(c in value for c in "\r\n"):
        return f"[{display}]({quote(value, safe=':/?=&%#@+~')})"
    return display


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"] + ["| " + " | ".join(row) + " |" for row in rows])


def _relation_label(edge, language):
    base = RELATION_LABELS[language][edge["relation"]]
    return f"{base} · {edge['label']}" if edge.get("label") else base


def _mermaid_label(value):
    return "".join(f"#{ord(char)};" if char in '&<>"`\\\n\r#|[]{}' else char for char in str(value))


def render(data, language, graph_data=None):
    t = LABELS[language]
    nodes = data["nodes"]
    graph_data = graph_data or data
    out = [f"# {t[0]} — {cell(data['project'])}", f"{t[1]}: {cell(data.get('updated_at'))}"]
    if not nodes:
        return "\n\n".join(out + [t[6]]) + "\n"
    graph = ["```mermaid", "flowchart LR"]
    graph_ids = {node["id"]: f"n{i}" for i, node in enumerate(graph_data["nodes"])}
    for node in graph_data["nodes"]:
        branches = list(dict.fromkeys(rev.get("branch") for rev in node.get("revisions", []) if rev.get("branch")))
        label = f"{node['id']}: {node['title']} / {', '.join(branches) or '—'} / {node['execution_status']}"
        # Mermaid quoted labels use numeric entities; do not expose raw syntax or code fences.
        label = _mermaid_label(label)
        graph.append(f'  {graph_ids[node["id"]]}["{label}"]')
    for edge in graph_data["edges"]:
        arrow = "-.->" if edge["relation"] in DEPENDENCY_RELATIONS or edge["relation"] == "compares_to" else "-->"
        graph.append(f'  {graph_ids[edge["from"]]} {arrow}|{_mermaid_label(_relation_label(edge, language))}| {graph_ids[edge["to"]]}')
    graph.append("```")
    if graph_data.get("_focus"):
        focus = graph_data["_focus"]
        out.append(("聚焦视图；下表保留完整索引。外部依赖上下文：" if language == "zh" else
                    "Focused diagram; tables retain the complete index. External dependency context: ")
                   + cell(", ".join(focus["context_ids"]) or "—"))
    out += ["\n".join(graph), f"## {t[2]}"]
    out.append(table([t[11], t[7], t[8], t[9], t[10], t[19]], [
        [cell(n["id"] + ": " + n["title"]), cell(n["study"]), cell(n["execution_status"]),
         cell("\n".join(n.get("changes", []))), cell("\n".join(n.get("findings", []) + ([n["decision"]] if n.get("decision") else []))), location(n.get("note_path"))]
        for n in nodes]))
    out.append("## 问题、结果与证据" if language == "zh" else "## Questions, results and evidence")
    out.append(table([t[11], "摘要 / 问题" if language == "zh" else "Summary / question",
                      "结果" if language == "zh" else "Results", "Evidence"], [
        [cell(n["id"]), cell("\n".join(value for value in (n.get("summary"), n.get("question")) if value)),
         cell("\n".join(n.get("results", []))), cell(", ".join(n.get("evidence", [])))] for n in nodes]))
    out.append("## 关系与依赖证据" if language == "zh" else "## Research relations and dependency evidence")
    out.append(table(["From → To", "Relation", "Label", "Evidence"], [
        [cell(edge["from"] + " → " + edge["to"]), cell(edge["relation"]),
         cell(_relation_label(edge, language)), cell(", ".join(edge.get("evidence", [])))] for edge in data["edges"]]))
    out.append(f"## {t[3]}")
    rows = []
    for node in nodes:
        for rev in node.get("revisions", []):
            rows.append([cell(node["id"]), cell(rev["id"]), cell(" / ".join(x for x in (rev.get("repo"), rev.get("host")) if x)),
                         cell(" / ".join(x for x in (rev.get("branch"), rev.get("commit")) if x)), cell(rev.get("dirty")), cell(rev.get("worktree")),
                         location(rev.get("code_snapshot")) + " / " + location(rev.get("patch_path")), cell(rev.get("observed_at"))])
    out.append(table([t[11], t[12], t[13], t[14], t[15], t[16], t[17], t[18]], rows))
    out.append(f"## {t[4]}")
    out.append(table([t[11], "Run", "Tracking URI / experiment", t[12], t[8]], [
        [cell(n["id"]), location(r.get("url"), r["run_id"]) if r.get("url") else cell(r["run_id"]),
         cell(r["tracking_uri"] + " / " + (r.get("experiment_id") or "—")), cell(r["revision_id"]), cell(r.get("status"))]
        for n in nodes for r in n.get("runs", [])]))
    out.append("## 执行记录（任意后端）" if language == "zh" else "## Executions (any backend)")
    out.append(table([t[11], "Execution / backend", t[8], t[18], "Host", t[21], t[12]], [
        [cell(n["id"]), cell(execution["id"] + " / " + (execution.get("backend") or "—")),
         cell(execution.get("status")), cell(execution.get("observed_at")), cell(execution.get("host")),
         location(execution.get("directory")), cell(execution.get("revision_id"))]
        for n in nodes for execution in n.get("executions", [])]))
    out.append(f"## {t[5]}")
    out.append(table([t[11], t[20], "Host", t[21], t[22]], [
        [cell(n["id"]), cell(p["role"]), cell(p.get("host")), location(p["location"]), cell(p["storage"])]
        for n in nodes for p in n.get("paths", [])]))
    return "\n\n".join(out) + "\n"


def _stable_digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _managed_id(kind, key):
    digest = _stable_digest(f"{MANAGED_BY}\0{kind}\0{key}")[:20]
    return f"mlflow-{kind}-{digest}"


def _managed(element):
    custom = element.get("customData")
    return isinstance(custom, dict) and custom.get("managedBy") == MANAGED_BY


def _managed_lookup(elements):
    found = {}
    for element in elements:
        if _managed(element):
            custom = element["customData"]
            kind, key = custom.get("kind"), custom.get("key")
            if isinstance(kind, str) and isinstance(key, str):
                found[(kind, key)] = element
    return found


def _managed_data(kind, key, **extra):
    return {"managedBy": MANAGED_BY, "kind": kind, "key": str(key), **extra}


def _text_width(text, font_size):
    """Conservative Excalifont width estimate used to add explicit line breaks."""
    width = 0.0
    for char in text:
        if char == "\t":
            width += font_size * 1.32
        elif char.isspace():
            width += font_size * 0.38
        elif unicodedata.east_asian_width(char) in ("F", "W"):
            width += font_size
        elif char in "ilI.,:;!'|`":
            width += font_size * 0.35
        elif char in "MW@%&":
            width += font_size * 0.82
        else:
            width += font_size * 0.64
    return width


def _wrap_paragraph(paragraph, max_width, font_size):
    if not paragraph:
        return [""]
    safe_width = max_width * 0.88
    words, lines, current = paragraph.split(" "), [], ""
    for word in words:
        candidate = word if not current else current + " " + word
        if _text_width(candidate, font_size) <= safe_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        if _text_width(word, font_size) <= safe_width:
            current = word
            continue
        fragment = ""
        for char in word:
            candidate = fragment + char
            if fragment and _text_width(candidate, font_size) > safe_width:
                lines.append(fragment)
                fragment = char
            else:
                fragment = candidate
        current = fragment
    if current or not lines:
        lines.append(current)
    return lines


def _wrap_text(value, max_width, font_size):
    lines = []
    for paragraph in str(value).split("\n"):
        lines.extend(_wrap_paragraph(paragraph, max_width, font_size))
    return "\n".join(lines)


def _line_count(text):
    return max(1, text.count("\n") + 1)


def _element_base(element_id, element_type, index, updated):
    digest = _stable_digest(element_id)
    return {
        "id": element_id,
        "type": element_type,
        "x": 0,
        "y": 0,
        "width": 0,
        "height": 0,
        "angle": 0,
        "strokeColor": "#1e1e1e",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": None,
        "seed": int(digest[:8], 16) & 0x7fffffff,
        "version": 1,
        "versionNonce": int(digest[8:16], 16) & 0x7fffffff,
        "isDeleted": False,
        "boundElements": None,
        "updated": updated,
        "link": None,
        "locked": False,
    }


def _valid_excalidraw(document, label="Excalidraw document", allow_legacy_managed_arrows=False):
    require(isinstance(document, dict), f"{label} must be an object")
    require(document.get("type") == "excalidraw" and document.get("version") == 2,
            f"{label} must be an Excalidraw version 2 document")
    require(isinstance(document.get("elements"), list), f"{label}.elements must be a list")
    require(isinstance(document.get("appState", {}), dict), f"{label}.appState must be an object")
    require(isinstance(document.get("files", {}), dict), f"{label}.files must be an object")
    ids = set()
    for element in document["elements"]:
        require(isinstance(element, dict), f"{label} contains a non-object element")
        element_id = element.get("id")
        require(isinstance(element_id, str) and bool(element_id), f"{label} contains an element with an invalid id")
        require(element_id not in ids, f"{label} contains duplicate element id: {element_id}")
        ids.add(element_id)
        require(isinstance(element.get("type"), str), f"Element {element_id} has an invalid type")
        for key in ("x", "y", "width", "height"):
            require(isinstance(element.get(key), (int, float)) and math.isfinite(element[key]),
                    f"Element {element_id}.{key} must be finite numeric data")
        negative_legacy_arrow = (allow_legacy_managed_arrows and _managed(element)
                                 and element.get("customData", {}).get("kind") == "edge"
                                 and element.get("type") == "arrow")
        require((element["width"] >= 0 and element["height"] >= 0) or negative_legacy_arrow,
                f"Element {element_id} width and height must be nonnegative")
        require(isinstance(element.get("isDeleted", False), bool), f"Element {element_id}.isDeleted must be boolean")
    return ids


def _load_existing_excalidraw(path):
    if not path.exists():
        return None
    require(path.is_file(), f"Excalidraw output is not a file: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid existing Excalidraw JSON in {path}: {exc}") from exc
    _valid_excalidraw(document, f"Existing Excalidraw file {path}", allow_legacy_managed_arrows=True)
    return document


def _element_box(element):
    x, y = element["x"], element["y"]
    if element.get("type") in ("arrow", "line") and isinstance(element.get("points"), list) and element["points"]:
        points = [(x + point[0], y + point[1]) for point in element["points"]
                  if isinstance(point, (list, tuple)) and len(point) == 2
                  and all(isinstance(coord, (int, float)) and math.isfinite(coord) for coord in point)]
    else:
        points = [(x, y), (x + element["width"], y + element["height"])]
    if not points:
        points = [(x, y), (x + element["width"], y + element["height"])]
    left, right = min(point[0] for point in points), max(point[0] for point in points)
    top, bottom = min(point[1] for point in points), max(point[1] for point in points)
    angle = float(element.get("angle", 0) or 0)
    if angle:
        center_x, center_y = (left + right) / 2, (top + bottom) / 2
        corners = [(left, top), (right, top), (right, bottom), (left, bottom)]
        rotated = [(center_x + math.cos(angle) * (px - center_x) - math.sin(angle) * (py - center_y),
                    center_y + math.sin(angle) * (px - center_x) + math.cos(angle) * (py - center_y))
                   for px, py in corners]
        left, right = min(p[0] for p in rotated), max(p[0] for p in rotated)
        top, bottom = min(p[1] for p in rotated), max(p[1] for p in rotated)
    pad = 18
    if element.get("type") in ("arrow", "line"):
        pad = 32
    return (left - pad, top - pad, right + pad, bottom + pad)


def _overlaps(box, other):
    return box[0] < other[2] and other[0] < box[2] and box[1] < other[3] and other[1] < box[3]


def _find_new_position(width, height, occupied, preferred=None):
    # Follow the research layout, then move down clear of all saved manual geometry.
    preferred_x, preferred_y = preferred or (LAYOUT_LEFT, LAYOUT_TOP)
    for slot in range(100000):
        x, y = preferred_x, preferred_y + slot * (height + NODE_GAP_Y)
        candidate = (x - 18, y - 18, x + width + 18, y + height + 18)
        if not any(_overlaps(candidate, item) for item in occupied):
            return x, y
    raise ValueError("Could not find a clear position for a new experiment node")


def _label_texts(language):
    if language == "zh":
        return {"status": "状态", "branches": "分支", "changes": "主要改动", "none": "—",
                "updated": "更新", "no_nodes": "尚无实验节点。", "results": "结果", "findings": "已确定发现",
                "decision": "决定", "summary": "摘要", "question": "问题", "revision": "最新代码",
                "executions": "执行", "observed": "观测", "note": "笔记", "context": "依赖上下文"}
    return {"status": "Status", "branches": "Branches", "changes": "Main changes", "none": "—",
            "updated": "Updated", "no_nodes": "No experiment nodes yet.", "results": "Results", "findings": "Agreed findings",
            "decision": "Decision", "summary": "Summary", "question": "Question", "revision": "Latest code",
            "executions": "Execution", "observed": "Observed", "note": "Notes", "context": "Dependency context"}


def _preserve_unchanged_timestamps(elements, previous):
    for element in elements:
        if not _managed(element):
            continue
        custom = element["customData"]
        old = previous.get((custom.get("kind"), custom.get("key")))
        if not old:
            continue
        current_without_timestamp = {key: value for key, value in element.items() if key != "updated"}
        old_without_timestamp = {key: value for key, value in old.items() if key != "updated"}
        if current_without_timestamp == old_without_timestamp and "updated" in old:
            element["updated"] = old["updated"]


def _new_text_element(element_id, key, text, x, y, width, height, font_size, color, index, updated,
                      parent_id, old=None):
    base = _element_base(element_id, "text", index, updated)
    base.update({
        "x": x, "y": y, "width": width, "height": height,
        "strokeColor": color, "backgroundColor": "transparent", "fillStyle": "solid",
        "strokeWidth": 1, "roughness": 0, "roundness": None,
        "text": text, "fontSize": font_size, "fontFamily": 5,
        "textAlign": "left", "verticalAlign": "top", "containerId": parent_id,
        "originalText": text, "autoResize": True, "lineHeight": 1.25,
        "boundElements": None,
        "customData": _managed_data("text", key),
    })
    if isinstance(old, dict):
        for prop in ("strokeColor", "backgroundColor", "fillStyle", "strokeWidth", "strokeStyle", "roughness", "opacity", "textAlign", "verticalAlign"):
            if prop in old:
                base[prop] = old[prop]
        if isinstance(old.get("fontSize"), (int, float)) and 16 <= old["fontSize"] <= 32:
            base["fontSize"] = old["fontSize"]
        # Text always stays inside its current container; geometry follows the saved parent.
    return base


def _preserved_shape(base, old, dynamic):
    if not isinstance(old, dict):
        return base
    result = dict(base)
    for key, value in old.items():
        if key not in dynamic:
            result[key] = value
    for key in dynamic:
        if key in base:
            result[key] = base[key]
    return result


def _node_content(node, labels, language):
    branches = list(dict.fromkeys(revision.get("branch") for revision in node.get("revisions", [])
                                  if revision.get("branch")))
    branches_text = ", ".join(branches) or labels["none"]
    title = f"{node['id']}: {node['title']}"
    if language == "zh":
        title = f"实验 {title}"
    sections = [title, f"{labels['status']}: {node['execution_status']}\n{labels['branches']}: {branches_text}"]
    if node.get("_context"):
        sections[0] += f"\n[{labels['context']}]"
    for key in ("summary", "question"):
        if node.get(key):
            sections.append(f"{labels[key]}: {_excerpt(node[key], 180)}")
    revisions = node.get("revisions", [])
    if revisions:
        revision = max(enumerate(revisions), key=lambda item: (item[1].get("observed_at") or "", item[0]))[1]
        identity = (revision.get("commit") or "")[:10]
        if not identity:
            identity = _short_path(revision["code_snapshot"]) if revision.get("code_snapshot") else labels["none"]
        dirty = " + dirty" if revision.get("dirty") else ""
        sections.append(f"{labels['revision']}: {revision['id']} · {identity}{dirty}")
    for key in ("changes", "results", "findings"):
        values = node.get(key, [])
        if values:
            displayed = values[:3]
            lines = [f"• {_excerpt(value, 160)}" for value in displayed]
            if len(values) > len(displayed):
                lines.append(f"+{len(values) - len(displayed)} → Markdown")
            sections.append(f"{labels[key]}:\n" + "\n".join(lines))
    if node.get("decision"):
        sections.append(f"{labels['decision']}: {_excerpt(node['decision'], 180)}")
    executions = node.get("executions", [])
    if executions:
        execution = max(enumerate(executions), key=lambda item: (item[1].get("observed_at") or "", item[0]))[1]
        identity = f"{execution.get('backend') or labels['none']} / {execution['id']}"
        lines = [f"{labels['executions']}: {identity} · {execution.get('status') or labels['none']}"]
        if execution.get("observed_at"):
            lines.append(f"{labels['observed']}: {execution['observed_at']}")
        if execution.get("revision_id"):
            lines.append(f"revision: {execution['revision_id']}")
        if len(executions) > 1:
            lines.append(f"+{len(executions) - 1} → Markdown")
        sections.append("\n".join(lines))
    elif node.get("runs"):
        run = node["runs"][-1]
        sections.append(f"MLflow: {run['run_id']} · {run.get('status') or labels['none']}\nrevision: {run['revision_id']}")
    return "\n\n".join(sections)


def _excerpt(value, limit):
    value = " ".join(value.split())
    return value if len(value) <= limit else value[:limit - 1] + "…"


def _short_path(value):
    parsed = urlsplit(value)
    path = parsed.path.rstrip("/")
    return path.rsplit("/", 1)[-1] or parsed.netloc or value


def _path_link(value, host=None):
    parsed = urlsplit(value)
    if parsed.scheme in ("http", "https", "file", "ssh", "sftp"):
        return quote(value, safe=":/?=&%#@+~")
    if parsed.scheme:
        return None
    if host:
        # A host label is not evidence of an SSH/SFTP endpoint or a local mount.
        return None
    if value.startswith("/"):
        return "file://" + quote(value, safe="/~")
    return quote(value, safe="/~")


def _node_links(node, labels):
    paths = node.get("paths", [])
    primary = node.get("display", {}).get("primary_path")
    chosen = []
    if primary:
        match = next((path for path in paths if path["location"] == primary), None)
        match = match or next((path for path in paths if path["role"] == primary), None)
        chosen.append(match or {"role": "path", "location": primary})
    executions = node.get("executions", [])
    for execution in reversed(executions):
        if execution.get("directory"):
            chosen.append({"role": labels["executions"], "location": execution["directory"], "host": execution.get("host")})
            break
    rank = {"output": 0, "run": 0, "checkpoint": 1, "data": 2, "source_document": 4}
    chosen.extend(sorted(paths, key=lambda path: rank.get(path["role"], 3)))
    unique, links = set(), []
    for path in chosen:
        target = path["location"]
        if target in unique:
            continue
        unique.add(target)
        host = f" [{path['host']}]" if path.get("host") else ""
        links.append({"label": f"{path['role']}{host}: {_short_path(target)}", "target": target,
                      "host": path.get("host")})
        if len(links) == 2:
            break
    if node.get("note_path"):
        links.append({"label": f"{labels['note']}: {_short_path(node['note_path'])}", "target": node["note_path"]})
    return links


def _layout_arc(edge):
    # Comparisons also need adjacent columns; this is a placement constraint only.
    if edge["relation"] in ("uses_model", "uses_data"):
        return edge["to"], edge["from"]
    return edge["from"], edge["to"]


def _initial_layout(data, metrics, language="zh"):
    """Topology columns align the main route; studies label local card clusters."""
    nodes = data["nodes"]
    ids = {node["id"] for node in nodes}
    outgoing, incoming, levels = {nid: set() for nid in ids}, {nid: set() for nid in ids}, {nid: 0 for nid in ids}
    predecessors = {nid: set() for nid in ids}
    for edge in data["edges"]:
        arc = _layout_arc(edge)
        if arc:
            source, target = arc
            outgoing[source].add(target)
            incoming[target].add(source)
            predecessors[target].add(source)
    order = {node["id"]: (node.get("display", {}).get("order") if node.get("display", {}).get("order") is not None else index, index)
             for index, node in enumerate(nodes)}
    queue = sorted((nid for nid in ids if not incoming[nid]), key=order.get)
    visited = set()
    while queue:
        nid = queue.pop(0)
        visited.add(nid)
        for target in sorted(outgoing[nid], key=order.get):
            levels[target] = max(levels[target], levels[nid] + 1)
            incoming[target].discard(nid)
            if not incoming[target]:
                queue.append(target)
                queue.sort(key=order.get)
    # Bound cycles; do not pretend they are an acyclic research chain.
    remaining = ids - visited
    if remaining:
        cycle_level = max((levels[nid] for nid in visited), default=-1) + 1
        for nid in remaining:
            levels[nid] = cycle_level
    gap = max([NODE_GAP_X] + [_edge_label_width(_relation_label(edge, language), 16) + 48 for edge in data["edges"]])
    node_groups = {}
    for node in sorted(nodes, key=lambda node: order[node["id"]]):
        group = node.get("display", {}).get("group") or node["study"]
        node_groups[node["id"]] = group
    parents = {nid: nid for nid in ids}

    def root(group):
        while parents[group] != group:
            group = parents[group]
        return group

    for edge in data["edges"]:
        left, right = root(edge["from"]), root(edge["to"])
        if left != right:
            parents[right] = left
    components = {}
    for node in sorted(nodes, key=lambda node: order[node["id"]]):
        components.setdefault(root(node["id"]), []).append(node)
    descendants = {}
    for nid in ids:
        pending, seen = list(outgoing[nid]), {nid}
        while pending:
            current = pending.pop()
            if current not in seen:
                seen.add(current)
                pending.extend(outgoing[current])
        descendants[nid] = len(seen) - 1
    blocks = []
    for component in components.values():
        widths, members_by_level = {}, {}
        for node in component:
            nid = node["id"]
            widths[levels[nid]] = max(widths.get(levels[nid], NODE_WIDTH), metrics[nid]["width"])
            members_by_level.setdefault(levels[nid], []).append(node)
        columns, width = {}, 0
        for level in sorted(widths):
            columns[level] = width
            width += widths[level] + gap
        width -= gap
        block_positions, block_headers, centers, bottom = {}, {}, {}, 0
        for level in sorted(members_by_level):
            def placement_key(node):
                nid = node["id"]
                upstream = [centers[source] for source in predecessors[nid] if source in centers]
                preferred = sum(upstream) / len(upstream) if upstream else 0
                explicit = node.get("display", {}).get("order")
                return (preferred, explicit if explicit is not None else -descendants[nid], order[nid])

            cursor, previous_group = 0, None
            for node in sorted(members_by_level[level], key=placement_key):
                nid, group = node["id"], node_groups[node["id"]]
                upstream = [centers[source] for source in predecessors[nid] if source in centers]
                preferred = sum(upstream) / len(upstream) - metrics[nid]["height"] / 2 if upstream else cursor
                new_group = group != previous_group
                y = max(cursor + (56 if new_group else 0), preferred)
                block_positions[nid] = (columns[level], y)
                if new_group:
                    block_headers[(group, nid)] = (columns[level], y - 50, widths[level])
                centers[nid] = y + metrics[nid]["height"] / 2
                cursor = y + metrics[nid]["height"] + NODE_GAP_Y
                bottom = max(bottom, y + metrics[nid]["height"])
                previous_group = group
        blocks.append((width, bottom, block_positions, block_headers))
    area = sum(width * height for width, height, _, _ in blocks)
    target_width = max([NODE_WIDTH * 2 + gap, min(2800, math.sqrt(area * 1.4))]
                       + [block[0] for block in blocks])
    # Pack disconnected components into free card-sized spaces, rather than reserving
    # a whole sparse bounding rectangle for a long main route.
    blocks.sort(key=lambda block: -len(block[2]))
    positions, headers, packed = {}, {}, []
    for width, height, block_positions, block_headers in blocks:
        candidates = {LAYOUT_LEFT, *(box[0] for box in packed), *(box[2] + 100 for box in packed)}
        rows = {LAYOUT_TOP, *(box[3] + 40 for box in packed)}
        choices = []
        for x in sorted(candidates):
            if x + width > LAYOUT_LEFT + target_width:
                continue
            for top in sorted(rows):
                boxes = [(x + position[0], top + position[1] - 56,
                          x + position[0] + metrics[nid]["width"], top + position[1] + metrics[nid]["height"] + 40)
                         for nid, position in block_positions.items()]
                if not any(_overlaps(box, occupied) for box in boxes for occupied in packed):
                    choices.append((top, x))
                    break
        top, x = min(choices)
        positions.update({nid: (x + position[0], top + position[1]) for nid, position in block_positions.items()})
        headers.update({group: (x + header[0], top + header[1], header[2]) for group, header in block_headers.items()})
        packed.extend((x + position[0], top + position[1] - 56,
                       x + position[0] + metrics[nid]["width"], top + position[1] + metrics[nid]["height"] + 40)
                      for nid, position in block_positions.items())
    return positions, headers


def _binding_list(values):
    seen, output = set(), []
    for value in values:
        if not isinstance(value, dict) or not isinstance(value.get("id"), str):
            continue
        identity = (value["id"], value.get("type"))
        if identity in seen:
            continue
        seen.add(identity)
        output.append(value)
    return output or None


def _edge_points(source, target, lane_offset=0):
    sx, sy, sw, sh = source["x"], source["y"], source["width"], source["height"]
    tx, ty, tw, th = target["x"], target["y"], target["width"], target["height"]
    scx, scy, tcx, tcy = sx + sw / 2, sy + sh / 2, tx + tw / 2, ty + th / 2
    dx, dy = tcx - scx, tcy - scy
    # Exit from facing sides for distinct columns, even across distant study bands.
    # A top/bottom exit here can send a dependency diagonally through sibling cards.
    if sx + sw <= tx or tx + tw <= sx:
        start_offset = max(-max(0, sh / 2 - 28), min(max(0, sh / 2 - 28), lane_offset))
        end_offset = max(-max(0, th / 2 - 28), min(max(0, th / 2 - 28), lane_offset))
        start = (sx + sw if dx >= 0 else sx, scy + start_offset)
        end = (tx if dx >= 0 else tx + tw, tcy + end_offset)
        start_focus = start_offset * 2 / max(1, sh)
        end_focus = end_offset * 2 / max(1, th)
    else:
        start_offset = max(-max(0, sw / 2 - 28), min(max(0, sw / 2 - 28), lane_offset))
        end_offset = max(-max(0, tw / 2 - 28), min(max(0, tw / 2 - 28), lane_offset))
        start = (scx + start_offset, sy + sh if dy >= 0 else sy)
        end = (tcx + end_offset, ty if dy >= 0 else ty + th)
        start_focus = start_offset * 2 / max(1, sw)
        end_focus = end_offset * 2 / max(1, tw)
    return start, end, start_focus, end_focus


def _segment_intersects_box(start, end, box):
    """Strict interior intersection for orthogonal routing; touching a boundary is safe."""
    left, top, right, bottom = box
    if start[0] == end[0]:
        return left < start[0] < right and max(min(start[1], end[1]), top) < min(max(start[1], end[1]), bottom)
    if start[1] == end[1]:
        return top < start[1] < bottom and max(min(start[0], end[0]), left) < min(max(start[0], end[0]), right)
    raise ValueError("Routing segments must be orthogonal")


def _simplify_route(points):
    compact = []
    for point in points:
        if compact and point == compact[-1]:
            continue
        if len(compact) >= 2 and ((compact[-2][0] == compact[-1][0] == point[0])
                                  or (compact[-2][1] == compact[-1][1] == point[1])):
            compact[-1] = point
        else:
            compact.append(point)
    return compact


def _route_edge(start, end, source, target, node_shapes, additional_boxes=()):
    """Find a short orthogonal path through gutters, with a visibility-grid fallback."""
    def anchor(point, shape):
        x, y = point
        if x == shape["x"]:
            return (x - 20, y)
        if x == shape["x"] + shape["width"]:
            return (x + 20, y)
        if y == shape["y"]:
            return (x, y - 20)
        return (x, y + 20)

    source_anchor, target_anchor = anchor(start, source), anchor(end, target)
    boxes = [_element_box(shape) for shape in node_shapes.values()] + list(additional_boxes)

    def clear(a, b):
        return not any(_segment_intersects_box(a, b, box) for box in boxes)

    sx, sy = source_anchor
    tx, ty = target_anchor
    middle_x, middle_y = (sx + tx) / 2, (sy + ty) / 2
    candidates = [
        [source_anchor, (middle_x, sy), (middle_x, ty), target_anchor],
        [source_anchor, (sx, middle_y), (tx, middle_y), target_anchor],
        [source_anchor, (sx, ty), target_anchor],
        [source_anchor, (tx, sy), target_anchor],
    ]
    for candidate in candidates:
        if all(clear(a, b) for a, b in zip(candidate, candidate[1:])):
            return _simplify_route([start] + candidate + [end])

    xs = sorted({sx, tx, *(coordinate for box in boxes for coordinate in (box[0], box[2]))})
    ys = sorted({sy, ty, *(coordinate for box in boxes for coordinate in (box[1], box[3]))})
    xs = [xs[0] - 64] + xs + [xs[-1] + 64]
    ys = [ys[0] - 64] + ys + [ys[-1] + 64]
    initial = (xs.index(sx), ys.index(sy), 0)
    goal = (xs.index(tx), ys.index(ty))
    distances, previous = {initial: 0}, {}
    pending = [(abs(sx - tx) + abs(sy - ty), 0, initial)]
    final = None
    while pending:
        _, cost, state = heapq.heappop(pending)
        if cost != distances.get(state):
            continue
        ix, iy, direction = state
        if (ix, iy) == goal:
            final = state
            break
        a = (xs[ix], ys[iy])
        for nx, ny, new_direction in ((ix - 1, iy, 1), (ix + 1, iy, 1), (ix, iy - 1, 2), (ix, iy + 1, 2)):
            if not (0 <= nx < len(xs) and 0 <= ny < len(ys)):
                continue
            b = (xs[nx], ys[ny])
            if not clear(a, b):
                continue
            new_cost = cost + abs(a[0] - b[0]) + abs(a[1] - b[1]) + (30 if direction and direction != new_direction else 0)
            next_state = (nx, ny, new_direction)
            if new_cost < distances.get(next_state, math.inf):
                distances[next_state], previous[next_state] = new_cost, state
                estimate = new_cost + abs(b[0] - tx) + abs(b[1] - ty)
                heapq.heappush(pending, (estimate, new_cost, next_state))
    if final is None:
        # Overlapping manually positioned cards may leave no free route. Keep their layout.
        return _simplify_route([start, (middle_x, start[1]), (middle_x, end[1]), end])
    path = []
    while final is not None:
        path.append((xs[final[0]], ys[final[1]]))
        final = previous.get(final)
    return _simplify_route([start] + list(reversed(path)) + [end])


def _edge_label_position(width, height, route, occupied):
    segments = sorted(zip(route, route[1:]), key=lambda pair: -abs(pair[1][0] - pair[0][0]) - abs(pair[1][1] - pair[0][1]))
    for offset_index in range(9):
        for start, end in segments:
            vertical = start[0] == end[0]
            half_size = width / 2 if vertical else height / 2
            offset = (0, -half_size, half_size, -48, 48, -96, 96, -160, 160)[offset_index]
            for fraction in (0.5, 0.35, 0.65, 0.2, 0.8):
                x = start[0] + (end[0] - start[0]) * fraction - width / 2
                y = start[1] + (end[1] - start[1]) * fraction - height / 2
                if vertical:
                    x += offset
                else:
                    y += offset
                box = (x, y, x + width, y + height)
                if not any(_overlaps(box, item) for item in occupied):
                    return x, y
    # Search nearby free boundaries instead of exiling a label to the far canvas edge.
    xs = {point[0] - width / 2 for point in route}
    ys = {point[1] - height / 2 for point in route}
    xs.update(coordinate for box in occupied for coordinate in (box[0] - width - 8, box[2] + 8))
    ys.update(coordinate for box in occupied for coordinate in (box[1] - height - 8, box[3] + 8))
    choices = []
    for x in sorted(xs):
        for y in sorted(ys):
            if any(_overlaps((x, y, x + width, y + height), box) for box in occupied):
                continue
            cx, cy = x + width / 2, y + height / 2
            distance = min(abs(cx - max(min(cx, max(a[0], b[0])), min(a[0], b[0])))
                           + abs(cy - max(min(cy, max(a[1], b[1])), min(a[1], b[1]))) for a, b in segments)
            midpoint_distance = abs(cx - (route[0][0] + route[-1][0]) / 2) + abs(cy - (route[0][1] + route[-1][1]) / 2)
            choices.append((distance, midpoint_distance, x, y))
    _, _, x, y = min(choices)
    return x, y


def _edge_label_width(text, font_size):
    return max(160, min(420, math.ceil(_text_width(text, font_size) / 0.88 + 24)))


def _label_route_distance(box, route):
    return min(max(0, min(start[0], end[0]) - box[2], box[0] - max(start[0], end[0]))
               + max(0, min(start[1], end[1]) - box[3], box[1] - max(start[1], end[1]))
               for start, end in zip(route, route[1:]))


def _edge_label_is_manual(shape, text=None):
    if not isinstance(shape, dict):
        return False
    custom = shape.get("customData", {})
    placement = custom.get("labelPlacement")
    if placement == "manual":
        return True
    if placement == "auto":
        auto_x, auto_y = custom.get("autoX"), custom.get("autoY")
        if not all(type(value) in (int, float) and math.isfinite(value) for value in (auto_x, auto_y)):
            return True
        return not (math.isclose(shape["x"], auto_x, abs_tol=1e-6, rel_tol=0)
                    and math.isclose(shape["y"], auto_y, abs_tol=1e-6, rel_tol=0))
    digest = _stable_digest(shape["id"])
    untouched = (placement is None and shape.get("version") == 1
                 and shape.get("seed") == int(digest[:8], 16) & 0x7fffffff
                 and shape.get("versionNonce") == int(digest[8:16], 16) & 0x7fffffff)
    if not untouched or not isinstance(text, dict):
        return True
    return not (math.isclose(text["x"], shape["x"] + 10, abs_tol=1e-6, rel_tol=0)
                and math.isclose(text["y"], shape["y"] + max(4, (shape["height"] - text["height"]) / 2),
                                 abs_tol=1e-6, rel_tol=0))


def _new_edge_label(edge, edge_key, edge_id, old_shape, old_text, start, end, updated, index, allocated, language,
                    route=None, occupied=None):
    text = _relation_label(edge, language)
    font_size = old_text.get("fontSize", 16) if old_text else 16
    if not isinstance(font_size, (int, float)) or not 16 <= font_size <= 32:
        font_size = 16
    width = _edge_label_width(text, font_size)
    if isinstance(old_shape, dict):
        if isinstance(old_shape.get("width"), (int, float)) and old_shape["width"] >= 60:
            width = max(width, old_shape["width"])
    height = math.ceil(_line_count(_wrap_text(text, width - 20, font_size)) * font_size * 1.25 + 2) + 16
    if isinstance(old_shape, dict):
        if isinstance(old_shape.get("height"), (int, float)) and old_shape["height"] >= 24:
            height = max(height, old_shape["height"])
    manual = _edge_label_is_manual(old_shape, old_text)
    if isinstance(old_shape, dict):
        x, y = old_shape["x"], old_shape["y"]
        box = (x, y, x + width, y + height)
        label_route = route or [start, end]
        if not manual:
            obstructed = any(_overlaps(box, item) for item in occupied or [])
            distance = _label_route_distance(box, label_route)
            if obstructed or distance > 12:
                new_x, new_y = _edge_label_position(width, height, label_route, occupied or [])
                new_box = (new_x, new_y, new_x + width, new_y + height)
                if obstructed or _label_route_distance(new_box, label_route) < distance:
                    x, y = new_x, new_y
    else:
        x, y = _edge_label_position(width, height, route or [start, end], occupied or [])
    label_id = allocated("edge-label", edge_key)
    placement = {"labelPlacement": "manual"} if manual else {"labelPlacement": "auto", "autoX": x, "autoY": y}
    base = _element_base(label_id, "rectangle", index(), updated)
    base.update({"x": x, "y": y, "width": width, "height": height,
                 "strokeColor": "#d0d7de", "backgroundColor": "#ffffff", "fillStyle": "solid",
                 "strokeWidth": 1, "roughness": 0, "roundness": {"type": 3},
                 "boundElements": None, "customData": _managed_data("edge-label", edge_key, **placement)})
    base = _preserved_shape(base, old_shape,
                            {"id", "type", "x", "y", "width", "height", "boundElements", "customData", "index", "updated", "isDeleted"})
    text_id = allocated("edge-text", edge_key)
    text_obj = _new_text_element(text_id, edge_key, text, x + 10, y + 8, max(40, width - 20), max(18, height - 12),
                                 font_size, "#495057", index(), updated, label_id, old_text)
    text_obj["text"] = _wrap_text(text, max(40, width - 20), text_obj["fontSize"])
    text_obj["originalText"] = text_obj["text"]
    text_obj["height"] = math.ceil(_line_count(text_obj["text"]) * text_obj["fontSize"] * text_obj["lineHeight"] + 2)
    base["height"] = max(height, text_obj["height"] + 16)
    text_obj["y"] = y + max(4, (base["height"] - text_obj["height"]) / 2)
    base["boundElements"] = [{"id": text_id, "type": "text"}]
    return base, text_obj


def _render_excalidraw(data, existing, language, relayout=False):
    labels = _label_texts(language)
    existing_elements = existing.get("elements", []) if existing else []
    previous = _managed_lookup(existing_elements)
    old_managed_ids = {element["id"] for element in existing_elements if _managed(element)}
    unmanaged = [dict(element) for element in existing_elements if not _managed(element)]
    unmanaged_ids = {element["id"] for element in unmanaged}
    occupied = []
    for element in existing_elements:
        if not element.get("isDeleted", False):
            if not relayout or not _managed(element):
                occupied.append(_element_box(element))

    allocated_ids = set(unmanaged_ids)
    generated_index = 0

    def index():
        nonlocal generated_index
        generated_index += 1
        return f"z{generated_index:08d}"

    def allocate(kind, key):
        base = _managed_id(kind, str(key))
        candidate, suffix = base, 0
        while candidate in allocated_ids:
            suffix += 1
            candidate = f"{base}-{suffix}"
        allocated_ids.add(candidate)
        return candidate

    updated = int(time.time() * 1000)
    generated = []
    node_shapes = {}
    metrics = {}
    for node in data["nodes"]:
        nid = node["id"]
        old_shape = previous.get(("node", nid))
        old_text = previous.get(("text", f"{nid}:body")) or previous.get(("text", f"{nid}:title"))
        width = node.get("display", {}).get("width") or NODE_WIDTH
        if old_shape and not relayout:
            width = old_shape.get("width", width)
        if not isinstance(width, (int, float)) or width < 180:
            width = NODE_WIDTH
        font_size = old_text.get("fontSize", 16) if old_text else 16
        if not isinstance(font_size, (int, float)) or not 16 <= font_size <= 32:
            font_size = 16
        content = _wrap_text(_node_content(node, labels, language), width - 44, font_size)
        text_height = math.ceil(_line_count(content) * font_size * 1.25 + 2)
        links = _node_links(node, labels)
        link_height = 0
        for link_index, link in enumerate(links):
            old_link_text = previous.get(("text", f"{nid}:link:{link_index}"))
            link_font = old_link_text.get("fontSize", 16) if old_link_text else 16
            if not isinstance(link_font, (int, float)) or not 16 <= link_font <= 32:
                link_font = 16
            link["font_size"] = link_font
            link["label"] = _wrap_text(_excerpt(link["label"], 90), width - 64, link_font)
            link["height"] = math.ceil(_line_count(link["label"]) * link_font * 1.25 + 16)
            link_height += link["height"] + 8
        height = text_height + 44 + link_height
        if old_shape and not relayout:
            height = max(height, old_shape["height"])
        metrics[nid] = {"width": float(width), "height": height, "text_height": text_height,
                        "font_size": font_size, "content": content, "links": links}
    initial_positions, group_headers = _initial_layout(data, metrics, language)

    title_key = "project-title"
    header_parent_id = allocate("header", title_key)
    old_header_parent = previous.get(("header", title_key))
    header_x = old_header_parent.get("x", 80) if old_header_parent else 80
    header_y = old_header_parent.get("y", 34) if old_header_parent else 34
    header_shape = _element_base(header_parent_id, "rectangle", index(), updated)
    header_shape.update({"x": header_x, "y": header_y, "width": 1100, "height": 112,
                         "strokeColor": "transparent", "backgroundColor": "transparent", "strokeWidth": 0,
                         "roughness": 0, "roundness": None, "boundElements": [],
                         "customData": _managed_data("header", title_key)})
    header_shape = _preserved_shape(header_shape, old_header_parent,
                                    {"id", "type", "x", "y", "width", "height", "boundElements", "customData", "index", "updated", "isDeleted"})
    generated.append(header_shape)
    header_text_id = allocate("header-text", "project-header")
    old_header_text = previous.get(("text", "project-header")) or previous.get(("text", "project-title"))
    diagram_title = (f"{data['project']} · 实验路径图" if language == "zh"
                     else f"Experiment map · {data['project']}")
    header_content = f"{diagram_title}\n{labels['updated']}: {data.get('updated_at') or labels['none']}"
    header_content += ("\n实线：研究路线；蓝色虚线：依赖（箭头指向使用的模型 / 数据或产物）" if language == "zh" else
                       "\nSolid: research routes; blue dashed: dependencies (arrows point to resources / products)")
    if data.get("_focus"):
        header_content += f"\nFocus: {len(data['nodes'])}/{data['_focus']['total_nodes']} · {labels['context']}: {len(data['_focus']['context_ids'])}"
    header_text = _new_text_element(header_text_id, "project-header", header_content, header_x + 22, header_y + 16,
                                    1056, 72, 22, "#1e1e1e", index(), updated, header_parent_id, old_header_text)
    header_text["text"] = _wrap_text(header_text["text"], header_text["width"], header_text["fontSize"])
    header_text["originalText"] = header_text["text"]
    header_text["height"] = max(72, math.ceil(_line_count(header_text["text"]) * header_text["fontSize"] * header_text["lineHeight"] + 2))
    header_shape["height"] = max(header_shape["height"], header_text["height"] + 32)
    header_shape["boundElements"] = [{"id": header_text_id, "type": "text"}]
    generated.append(header_text)

    legacy_studies = set()
    for (group, first_member), (group_x, group_y, group_width) in group_headers.items():
        key = "study:" + json.dumps([group, first_member], ensure_ascii=False, separators=(",", ":"))
        old_group = previous.get(("study", key))
        old_text_key = key
        if not old_group and group not in legacy_studies:
            old_text_key = f"study:{group}"
            old_group = previous.get(("study", old_text_key))
            legacy_studies.add(group)
        if old_group and not relayout:
            group_x, group_y = old_group["x"], old_group["y"]
        elif not relayout and ("node", first_member) in previous:
            member = previous[("node", first_member)]
            group_x, group_y = member["x"], member["y"] - 50
        else:
            member = next(node for node in data["nodes"] if node["id"] == first_member)
            display = member.get("display", {})
            if display.get("x") is not None:
                group_x, group_y = display["x"], display["y"] - 50
        group_id = allocate("study", key)
        group_shape = _element_base(group_id, "rectangle", index(), updated)
        group_shape.update({"x": group_x, "y": group_y, "width": max(460, group_width), "height": 40,
                            "strokeWidth": 0, "strokeColor": "transparent", "roughness": 0,
                            "customData": _managed_data("study", key)})
        group_shape = _preserved_shape(group_shape, old_group,
                                       {"id", "type", "x", "y", "width", "height", "boundElements", "customData", "index", "updated", "isDeleted"})
        group_text_id = allocate("study-text", key)
        group_text = _new_text_element(group_text_id, key, group, group_x + 6, group_y + 6,
                                       max(448, group_width - 12), 28, 20, "#495057", index(), updated,
                                       group_id, previous.get(("text", key)) or previous.get(("text", old_text_key)))
        group_text["text"] = _wrap_text(group, group_text["width"], group_text["fontSize"])
        group_text["originalText"] = group_text["text"]
        group_text["height"] = math.ceil(_line_count(group_text["text"]) * group_text["fontSize"] * 1.25 + 2)
        group_shape["height"] = group_text["height"] + 12
        group_shape["boundElements"] = [{"id": group_text_id, "type": "text"}]
        generated.extend((group_shape, group_text))

    previous_node_keys = {key for kind, key in previous if kind == "node"}
    node_order = ([node for node in data["nodes"] if node["id"] in previous_node_keys]
                  + [node for node in data["nodes"] if node["id"] not in previous_node_keys])
    for node in node_order:
        node_key = node["id"]
        shape_id = allocate("node", node_key)
        old_shape = previous.get(("node", node_key))
        old_text = previous.get(("text", f"{node_key}:body")) or previous.get(("text", f"{node_key}:title"))
        metric = metrics[node_key]
        saved_width, font_size = metric["width"], metric["font_size"]
        text_width = max(100, saved_width - 44)
        content, text_height = metric["content"], metric["text_height"]
        needed_height = metric["height"]
        if old_shape and not relayout:
            x, y = old_shape["x"], old_shape["y"]
            saved_height = old_shape.get("height", needed_height)
            height = max(needed_height, saved_height if isinstance(saved_height, (int, float)) else needed_height)
        else:
            display = node.get("display", {})
            preferred = initial_positions[node_key]
            if display.get("x") is not None:
                preferred = (display["x"], display["y"])
            x, y = _find_new_position(saved_width, needed_height, occupied, preferred)
            height = needed_height
        fill, stroke = STATUS_COLORS.get(node["execution_status"], STATUS_COLORS["unknown"])
        update_default_colors = False
        update_default_stroke = False
        old_custom = old_shape.get("customData", {}) if old_shape else {}
        old_palette = STATUS_COLORS.get(old_custom.get("status"))
        if old_shape and old_palette:
            update_default_colors = old_shape.get("backgroundColor") == old_custom.get("defaultBackgroundColor", old_palette[0])
            update_default_stroke = old_shape.get("strokeColor") == old_custom.get("defaultStrokeColor", old_palette[1])
        shape = _element_base(shape_id, "rectangle", index(), updated)
        shape.update({"x": x, "y": y, "width": saved_width, "height": height,
                      "strokeColor": stroke, "backgroundColor": fill, "fillStyle": "solid",
                      "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1,
                      "roundness": {"type": 3}, "boundElements": [],
                      "customData": _managed_data("node", node_key, status=node["execution_status"],
                                                  study=node["study"], group=node.get("display", {}).get("group") or node["study"],
                                                  context=bool(node.get("_context")),
                                                  defaultBackgroundColor=fill, defaultStrokeColor=stroke)})
        shape = _preserved_shape(shape, old_shape,
                                 {"id", "type", "x", "y", "width", "height", "boundElements", "customData", "index", "updated", "isDeleted"})
        if update_default_colors:
            shape["backgroundColor"] = fill
        if update_default_stroke:
            shape["strokeColor"] = stroke
        shape["width"], shape["height"] = saved_width, height
        node_shapes[node_key] = shape
        generated.append(shape)
        occupied.append(_element_box(shape))

        bound_texts = []
        if old_shape and isinstance(old_shape.get("boundElements"), list):
            bound_texts.extend(binding for binding in old_shape["boundElements"]
                               if isinstance(binding, dict) and binding.get("id") in unmanaged_ids
                               and binding.get("type") == "arrow")
        text_key = f"{node_key}:body"
        text_id = allocate("node-text", text_key)
        element = _new_text_element(text_id, text_key, content, x + 22, y + 22, text_width,
                                    text_height, font_size, "#1e1e1e", index(), updated, shape_id, old_text)
        element["text"] = _wrap_text(content, text_width, element["fontSize"])
        element["originalText"] = element["text"]
        element["height"] = math.ceil(_line_count(element["text"]) * element["fontSize"] * element["lineHeight"] + 2)
        shape["height"] = max(shape["height"], element["height"] + 44)
        shape["boundElements"] = bound_texts + [{"id": text_id, "type": "text"}]
        generated.append(element)
        link_y = y + 22 + element["height"] + 12
        for link_index, link in enumerate(metric["links"]):
            link_key = f"{node_key}:link:{link_index}"
            link_id = allocate("node-link", link_key)
            old_link = previous.get(("node-link", link_key))
            link_shape = _element_base(link_id, "rectangle", index(), updated)
            link_url = _path_link(link["target"], link.get("host"))
            if link_url is None and node.get("note_path"):
                link_url = _path_link(node["note_path"])
            link_shape.update({"x": x + 22, "y": link_y, "width": saved_width - 44, "height": link["height"],
                               "strokeColor": "#a5d8ff", "backgroundColor": "#f8fbff", "strokeWidth": 1,
                               "roughness": 0, "roundness": {"type": 3}, "link": link_url,
                               "customData": _managed_data("node-link", link_key, target=link["target"], host=link.get("host"),
                                                           autoX=x + 22, autoY=link_y)})
            link_shape = _preserved_shape(link_shape, old_link,
                                          {"id", "type", "x", "y", "width", "height", "link", "boundElements", "customData", "index", "updated", "isDeleted"})
            if old_link and not relayout:
                old_custom = old_link.get("customData", {})
                if (old_custom.get("autoX") is not None and old_custom.get("autoY") is not None
                        and (old_link["x"], old_link["y"]) != (old_custom["autoX"], old_custom["autoY"])):
                    link_shape["x"], link_shape["y"] = old_link["x"], old_link["y"]
            link_text_id = allocate("node-link-text", link_key)
            link_text = _new_text_element(link_text_id, link_key, link["label"], link_shape["x"] + 10, link_shape["y"] + 8,
                                          saved_width - 64, link["height"] - 16, link["font_size"], "#1864ab", index(), updated, link_id,
                                          previous.get(("text", link_key)))
            link_text["link"] = link_url
            link_shape["boundElements"] = [{"id": link_text_id, "type": "text"}]
            generated.extend((link_shape, link_text))
            link_y += link["height"] + 8
        shape["height"] = max(shape["height"], link_y - y + 8)

    # Regenerate current relations from facts. Existing user styling and label positions survive.
    occurrences = {}
    pair_counts = {}
    edge_records = []
    for edge in data["edges"]:
        pair = tuple(sorted((edge["from"], edge["to"])))
        pair_counts[pair] = pair_counts.get(pair, 0) + 1
        identity = (edge["from"], edge["relation"], edge["to"])
        occurrence = occurrences.get(identity, 0)
        occurrences[identity] = occurrence + 1
        edge_key = json.dumps([*identity, occurrence], ensure_ascii=False, separators=(",", ":"))
        old_edge_key = edge_key
        old_arrow = previous.get(("edge", edge_key))
        if not old_arrow:
            candidates = []
            for (kind, candidate_key), candidate in previous.items():
                if kind != "edge":
                    continue
                try:
                    old_from, _, old_to, old_occurrence = json.loads(candidate_key)
                except (TypeError, ValueError):
                    continue
                if old_from == edge["from"] and old_to == edge["to"] and old_occurrence == occurrence:
                    candidates.append((candidate_key, candidate))
            if len(candidates) == 1:
                old_edge_key, old_arrow = candidates[0]
        old_label = previous.get(("edge-label", edge_key)) or previous.get(("edge-label", old_edge_key))
        old_label_text = previous.get(("text", edge_key)) or previous.get(("text", old_edge_key))
        edge_records.append((edge, edge_key, old_arrow, old_label, old_label_text))
    pair_occurrences = {}
    label_occupied = [_element_box(shape) for shape in node_shapes.values()]
    heading_boxes = [_element_box(element) for element in generated
                     if element.get("customData", {}).get("kind") in ("study", "header")]
    label_occupied.extend(heading_boxes)
    label_occupied.extend(_element_box(element) for element in unmanaged
                          if not element.get("isDeleted", False) and element.get("type") not in ("arrow", "line"))
    if not relayout:
        label_occupied.extend(_element_box(old_label) for _, _, _, old_label, old_text in edge_records
                              if _edge_label_is_manual(old_label, old_text))
    edge_arrows, edge_labels = [], []
    for edge, edge_key, old_arrow, old_label, old_label_text in edge_records:
        pair = tuple(sorted((edge["from"], edge["to"])))
        pair_occurrence = pair_occurrences.get(pair, 0)
        pair_occurrences[pair] = pair_occurrence + 1
        lane_offset = (pair_occurrence - (pair_counts[pair] - 1) / 2) * 64
        if edge["from"] != pair[0]:
            lane_offset = -lane_offset
        start, end, start_focus, end_focus = _edge_points(node_shapes[edge["from"]], node_shapes[edge["to"]], lane_offset)
        route = _route_edge(start, end, node_shapes[edge["from"]], node_shapes[edge["to"]], node_shapes,
                            heading_boxes)
        if len(route) < 2:
            route = [start, end]
        route_points = [[point[0] - start[0], point[1] - start[1]] for point in route]
        arrow_id = allocate("edge", edge_key)
        arrow = _element_base(arrow_id, "arrow", index(), updated)
        arrow_width = max(point[0] for point in route) - min(point[0] for point in route)
        arrow_height = max(point[1] for point in route) - min(point[1] for point in route)
        dependency = edge["relation"] in DEPENDENCY_RELATIONS
        edge_style = "dashed" if dependency or edge["relation"] == "compares_to" else "solid"
        edge_color = "#1971c2" if dependency else "#495057"
        arrow.update({"x": start[0], "y": start[1], "width": arrow_width, "height": arrow_height,
                      "points": route_points,
                      "strokeColor": edge_color, "backgroundColor": "transparent", "fillStyle": "solid",
                      "strokeWidth": 2, "strokeStyle": edge_style,
                      "roughness": 0, "roundness": None,
                      "startBinding": {"elementId": node_shapes[edge["from"]]["id"], "focus": start_focus, "gap": 2},
                      "endBinding": {"elementId": node_shapes[edge["to"]]["id"], "focus": end_focus, "gap": 2},
                      "lastCommittedPoint": None, "startArrowhead": None, "endArrowhead": "arrow",
                      "boundElements": None, "customData": _managed_data("edge", edge_key, relation=edge["relation"],
                                                                        label=edge.get("label"), evidence=edge.get("evidence", []),
                                                                        category="dependency" if dependency else "research")})
        relation_changed = bool(old_arrow and old_arrow.get("customData", {}).get("relation") != edge["relation"])
        arrow = _preserved_shape(arrow, old_arrow,
                                 {"id", "type", "x", "y", "width", "height", "points", "startBinding", "endBinding", "boundElements", "customData", "index", "updated", "isDeleted"})
        if relation_changed:
            arrow["strokeStyle"] = edge_style
            arrow["strokeColor"] = edge_color
        arrow.update({"x": start[0], "y": start[1], "width": arrow_width, "height": arrow_height,
                      "points": route_points,
                      "roundness": None,
                      "startBinding": {"elementId": node_shapes[edge["from"]]["id"], "focus": start_focus, "gap": 2},
                      "endBinding": {"elementId": node_shapes[edge["to"]]["id"], "focus": end_focus, "gap": 2}})
        edge_arrows.append(arrow)
        node_shapes[edge["from"]]["boundElements"].append({"id": arrow_id, "type": "arrow"})
        node_shapes[edge["to"]]["boundElements"].append({"id": arrow_id, "type": "arrow"})

        if relayout:
            old_label = None
        label_shape, label_text = _new_edge_label(edge, edge_key, arrow_id, old_label, old_label_text,
                                                  start, end, updated, index, allocate, language,
                                                  route=route, occupied=label_occupied)
        edge_labels.extend((label_shape, label_text))
        if not _edge_label_is_manual(label_shape):
            label_occupied.append(_element_box(label_shape))
    generated.extend(edge_arrows)
    generated.extend(edge_labels)

    # Keep manual annotations and their bindings. Remove references to managed elements that facts removed,
    # then rebuild bindings to any retained managed nodes from the preserved manual arrows.
    current_managed_ids = {element["id"] for element in generated}
    current_node_shape_ids = {shape["id"] for shape in node_shapes.values()}
    for element in unmanaged:
        if element.get("type") == "arrow":
            for endpoint in ("startBinding", "endBinding"):
                binding = element.get(endpoint)
                if isinstance(binding, dict):
                    target_id = binding.get("elementId")
                    if target_id in old_managed_ids and target_id not in current_managed_ids:
                        element[endpoint] = None
                    elif target_id in current_node_shape_ids:
                        target = next(shape for shape in node_shapes.values() if shape["id"] == target_id)
                        target["boundElements"] = (target.get("boundElements") or []) + [{"id": element["id"], "type": "arrow"}]
        if element.get("type") == "text" and element.get("containerId") in old_managed_ids:
            # Keep user text, but detach it so the managed card retains its single bound text.
            element["containerId"] = None
        bindings = element.get("boundElements")
        if isinstance(bindings, list):
            element["boundElements"] = _binding_list(binding for binding in bindings
                                                      if isinstance(binding, dict) and
                                                      (binding.get("id") not in old_managed_ids or binding.get("id") in current_managed_ids))
    for shape in node_shapes.values():
        shape["boundElements"] = _binding_list(shape.get("boundElements") or [])

    if not data["nodes"]:
        empty_key = "empty-state"
        empty_id = allocate("empty-state", empty_key)
        old_empty = previous.get(("empty-state", empty_key))
        empty_x, empty_y = (old_empty.get("x", LAYOUT_LEFT), old_empty.get("y", LAYOUT_TOP)) if old_empty else (LAYOUT_LEFT, LAYOUT_TOP)
        empty_box = _element_base(empty_id, "rectangle", index(), updated)
        empty_box.update({"x": empty_x, "y": empty_y, "width": 460, "height": 72,
                          "strokeColor": "#d0d7de", "backgroundColor": "#f8f9fa", "strokeWidth": 1,
                          "roughness": 0, "roundness": {"type": 3}, "boundElements": [],
                          "customData": _managed_data("empty-state", empty_key)})
        empty_box = _preserved_shape(empty_box, old_empty,
                                     {"id", "type", "x", "y", "width", "height", "boundElements", "customData", "index", "updated", "isDeleted"})
        empty_text_id = allocate("empty-text", empty_key)
        empty_text = _new_text_element(empty_text_id, empty_key, labels["no_nodes"], empty_x + 20, empty_y + 22,
                                       420, 28, 16, "#6c757d", index(), updated, empty_id,
                                       previous.get(("text", empty_key)))
        empty_text["text"] = _wrap_text(empty_text["text"], empty_text["width"], empty_text["fontSize"])
        empty_text["originalText"] = empty_text["text"]
        empty_text["height"] = max(28, math.ceil(_line_count(empty_text["text"]) * empty_text["fontSize"] * empty_text["lineHeight"] + 2))
        empty_box["height"] = max(empty_box["height"], empty_text["height"] + 44)
        empty_box["boundElements"] = [{"id": empty_text_id, "type": "text"}]
        generated.extend((empty_box, empty_text))

    # Array order supplies the paint order. Let native Excalidraw restore its
    # fractional indices; fabricated indices can fail beside manual elements.
    _preserve_unchanged_timestamps(generated, previous)
    document = dict(existing) if existing else {}
    document.update({"type": "excalidraw", "version": 2, "source": (existing or {}).get("source", "https://excalidraw.com"),
                     "elements": generated + unmanaged,
                     "appState": (existing or {}).get("appState", {"viewBackgroundColor": "#ffffff", "gridSize": 20}),
                     "files": (existing or {}).get("files", {})})
    _validate_managed_bindings(document)
    _valid_excalidraw(document, "Rendered Excalidraw document")
    return document


def _validate_managed_bindings(document):
    by_id = {element["id"]: element for element in document["elements"]}
    for element in document["elements"]:
        if not _managed(element):
            continue
        kind = element["customData"].get("kind")
        if element.get("type") == "text":
            parent_id = element.get("containerId")
            require(parent_id in by_id, f"Managed text {element['id']} has no container")
            parent = by_id[parent_id]
            text_bindings = [binding for binding in (parent.get("boundElements") or [])
                             if isinstance(binding, dict) and binding.get("type") == "text"]
            require(len(text_bindings) == 1,
                    f"Managed text container {parent_id} must bind exactly one text element")
            require(any(binding.get("id") == element["id"] and binding.get("type") == "text"
                        for binding in (parent.get("boundElements") or [])),
                    f"Managed text {element['id']} is not bound by its container")
            require(element.get("fontFamily") == 5, f"Managed text {element['id']} must use fontFamily 5")
            require(element.get("originalText") == element.get("text"),
                    f"Managed text {element['id']} has inconsistent originalText")
            require(isinstance(element.get("autoResize"), bool), f"Managed text {element['id']} needs autoResize")
            require(isinstance(element.get("lineHeight"), (int, float)) and element["lineHeight"] > 0,
                    f"Managed text {element['id']} needs a positive lineHeight")
        if kind == "edge":
            require(element.get("startArrowhead") is None and element.get("endArrowhead") == "arrow",
                    f"Managed arrow {element['id']} needs a directed arrowhead")
            for endpoint in ("startBinding", "endBinding"):
                binding = element.get(endpoint)
                require(isinstance(binding, dict) and binding.get("elementId") in by_id,
                        f"Managed arrow {element['id']} has an invalid {endpoint}")
                target = by_id[binding["elementId"]]
                require(any(item.get("id") == element["id"] and item.get("type") == "arrow"
                            for item in (target.get("boundElements") or [])),
                        f"Managed arrow {element['id']} is not bound by endpoint {target['id']}")


def _serialize_excalidraw(document):
    # Round-trip as an additional structural check before touching output paths.
    result = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    _valid_excalidraw(json.loads(result), "Serialized Excalidraw document")
    return result


def _output_mode(path):
    if path.exists():
        require(path.is_file(), f"Output is not a file: {path}")
        return path.stat().st_mode & 0o777
    current_umask = os.umask(0)
    os.umask(current_umask)
    return 0o666 & ~current_umask


def _stage_output(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = stream.name
            stream.write(content)
            os.fchmod(stream.fileno(), mode)
        return temporary
    except Exception:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
        raise


def _write_outputs(outputs):
    changed = []
    for path, content in outputs:
        if path.exists() and path.is_file() and path.read_text(encoding="utf-8") == content:
            continue
        changed.append((path, content, _output_mode(path)))
    staged = []
    try:
        for path, content, mode in changed:
            staged.append((path, _stage_output(path, content, mode)))
        for path, temporary in staged:
            os.replace(temporary, path)
    finally:
        for _, temporary in staged:
            if os.path.exists(temporary):
                os.unlink(temporary)


def _focus_registry(data, studies, node_ids):
    if not studies and not node_ids:
        return data
    known_ids = {node["id"] for node in data["nodes"]}
    known_studies = {node["study"] for node in data["nodes"]}
    require(set(node_ids) <= known_ids, "Unknown focus node: " + ", ".join(sorted(set(node_ids) - known_ids)))
    require(set(studies) <= known_studies, "Unknown focus study: " + ", ".join(sorted(set(studies) - known_studies)))
    selected = {node["id"] for node in data["nodes"] if node["study"] in studies or node["id"] in node_ids}
    included = set(selected)
    while True:
        previous = set(included)
        for edge in data["edges"]:
            if edge["relation"] in ("uses_model", "uses_data") and edge["from"] in included:
                included.add(edge["to"])
            elif edge["relation"] == "produces" and edge["to"] in included:
                included.add(edge["from"])
        if included == previous:
            break
    context_ids = [node["id"] for node in data["nodes"] if node["id"] in included - selected]
    return {**data, "nodes": [{**node, "_context": node["id"] in context_ids}
                              for node in data["nodes"] if node["id"] in included],
            "edges": [edge for edge in data["edges"] if edge["from"] in included and edge["to"] in included],
            "_focus": {"context_ids": context_ids, "total_nodes": len(data["nodes"])}}


def _overview_helpers():
    # Loading by path also works when this script is imported via spec_from_file_location.
    global _OVERVIEW_MODULE
    if "_OVERVIEW_MODULE" not in globals():
        spec = importlib.util.spec_from_file_location("experiment_overview", Path(__file__).with_name("experiment_overview.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _OVERVIEW_MODULE = module
    return _OVERVIEW_MODULE


def _overview_registry(data, language="zh", group=None):
    return _overview_helpers().prepare(data, language, group)


def render_overview(data, language="zh", group=None):
    prepared = data if "_overview" in data else _overview_registry(data, language, group)
    return _overview_helpers().markdown(prepared, language, globals())


def _render_overview_excalidraw(data, existing=None, language="zh", relayout=False, group=None, detail_path=None):
    prepared = data if "_overview" in data else _overview_registry(data, language, group)
    return _overview_helpers().excalidraw(prepared, existing, language, globals(), relayout=relayout, detail_path=detail_path)


def _overview_output(path, group=None):
    suffix = ".overview"
    if group is not None:
        slug = "".join(char if char.isascii() and (char.isalnum() or char in "-_") else "-" for char in group).strip("-")[:40] or "group"
        suffix += ".group-" + slug + "-" + _stable_digest(group)[:8]
    return path.with_name(path.stem + suffix + path.suffix)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--excalidraw-output", type=Path)
    parser.add_argument("--format", choices=("both", "excalidraw", "markdown"), default="both")
    parser.add_argument("--view", choices=("detailed", "overview", "both"), default="both")
    parser.add_argument("--overview-group", help="Render only an overview group into separate suffixed outputs; does not touch the overall maps")
    parser.add_argument("--lang", choices=LABELS, default="zh")
    parser.add_argument("--relayout", action="store_true", help="Recompute managed positions; preserve manual annotations and styling")
    parser.add_argument("--study", action="append", default=[], help="Focus diagram on a study; repeatable, includes external dependencies")
    parser.add_argument("--node", action="append", default=[], help="Focus diagram on a node ID; repeatable, union with --study")
    args = parser.parse_args()
    outputs = []
    try:
        require(args.overview_group is None or args.view != "detailed", "--overview-group requires --view overview or both")
        default_base = args.registry
        if args.study or args.node:
            selection = json.dumps([sorted(set(args.study)), sorted(set(args.node))], ensure_ascii=False)
            default_base = args.registry.with_name(args.registry.stem + ".focus-" + _stable_digest(selection)[:10] + ".json")
        markdown_output = args.output or default_base.with_suffix(".md")
        excalidraw_output = args.excalidraw_output or default_base.with_suffix(".excalidraw")
        detailed = args.view in ("both", "detailed") and args.overview_group is None
        overview = args.view in ("both", "overview")
        overview_markdown = _overview_output(markdown_output, args.overview_group)
        overview_excalidraw = _overview_output(excalidraw_output, args.overview_group)
        active_paths = []
        for enabled, md, diagram in ((detailed, markdown_output, excalidraw_output), (overview, overview_markdown, overview_excalidraw)):
            if enabled and args.format in ("both", "markdown"):
                active_paths.append(md)
            if enabled and args.format in ("both", "excalidraw"):
                active_paths.append(diagram)
        resolved_paths = [path.resolve() for path in active_paths]
        require(args.registry.resolve() not in resolved_paths, "Output must differ from source registry")
        require(len(set(resolved_paths)) == len(resolved_paths), "Markdown and Excalidraw outputs must differ")
        data = json.loads(args.registry.read_text(encoding="utf-8"))
        validate(data)
        focused = _focus_registry(data, args.study, args.node)
        if detailed and args.format in ("both", "markdown"):
            outputs.append((markdown_output, render(data, args.lang, focused)))
        if detailed and args.format in ("both", "excalidraw"):
            existing = _load_existing_excalidraw(excalidraw_output)
            document = _render_excalidraw(focused, existing, args.lang, relayout=args.relayout)
            outputs.append((excalidraw_output, _serialize_excalidraw(document)))
        if overview:
            prepared = _overview_registry(focused, args.lang, args.overview_group)
            if args.format in ("both", "markdown"):
                outputs.append((overview_markdown, render_overview(prepared, args.lang)))
            if args.format in ("both", "excalidraw"):
                existing = _load_existing_excalidraw(overview_excalidraw)
                document = _render_overview_excalidraw(prepared, existing, args.lang, relayout=args.relayout,
                                                      detail_path=overview_markdown.name)
                outputs.append((overview_excalidraw, _serialize_excalidraw(document)))
        _write_outputs(outputs)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    for output, _ in outputs:
        print(output.resolve())


if __name__ == "__main__":
    main()
