"""Compact experiment maps; shared renderer primitives are supplied by the caller.

No topology is guessed from titles, IDs, groups or node order. Registry edges
remain the only evidence for research relationships.
"""
import json
import math
import time


WIDTH = 460
GAP_X = 120
GAP_Y = 140
FONT = 22
EDGE_FONT = 20


def prepare(data, language="zh", group=None):
    """Resolve explicit fields and conservative fallbacks without editing facts."""
    zh = language == "zh"
    missing = "未整理（见详情）" if zh else "Not curated (see details)"
    nodes, notices = [], []
    groups = set()
    for index, node in enumerate(data["nodes"]):
        spec = node.get("overview", {})
        resolved_group = spec.get("group") or node.get("display", {}).get("group") or node["study"]
        groups.add(resolved_group)
        if not spec.get("include", True) or node.get("_context"):
            continue
        if group is not None and group != resolved_group:
            continue
        title = spec.get("title") or node["title"]
        result = spec.get("result") or ("；".join(node.get("results", [])) or missing)
        nodes.append({**node, "_overview": {
            "title": title, "group": resolved_group,
            "order": spec.get("order", node.get("display", {}).get("order", index)),
            "config": spec.get("config", []), "loss": spec.get("loss") or missing,
            "result": result, "detail_path": spec.get("detail_path") or node.get("note_path"),
        }})
        if not spec:
            notices.append((f"{node['id']}: 未提供 overview；仅回退标题/分组/顺序和 results，配置与 loss 待整理。" if zh else
                            f"{node['id']}: no overview metadata; only title/group/order/results fall back; config and loss need curation."))
    if group is not None and group not in groups:
        raise ValueError(f"Unknown overview group: {group}")
    # Null display.order is supported by the original schema.
    indices = {node["id"]: index for index, node in enumerate(data["nodes"])}
    nodes.sort(key=lambda node: (node["_overview"]["order"] if node["_overview"]["order"] is not None
                                 else indices[node["id"]], indices[node["id"]]))
    selected = {node["id"] for node in nodes}
    by_id = {node["id"]: node for node in data["nodes"]}
    research = [edge for edge in data["edges"] if edge["relation"] in
                ("derived_from", "continues_from", "compares_to", "merges_from")
                and edge.get("overview", {}).get("show", True)]
    edges = []

    def labelled(edge):
        spec = edge.get("overview", {})
        label = spec.get("label") or edge.get("label")
        if not label:
            label = "具体改动未整理 → 详情" if zh else "Change not curated → details"
            notices.append((f"{edge['from']} → {edge['to']}: 关系已记录，具体改动未整理。" if zh else
                            f"{edge['from']} → {edge['to']}: recorded relation; change label not curated."))
        return {**edge, "label": label}

    outgoing, incoming = {}, {}
    for edge in research:
        outgoing.setdefault(edge["from"], []).append(edge)
        incoming.setdefault(edge["to"], []).append(edge)
        if edge["from"] in selected and edge["to"] in selected:
            edges.append(labelled(edge))
    # Bridge only an explicitly hidden, unbranched derived_from chain. Comparison,
    # continuation, group filtering and edge.show=false never authorize a bridge.
    for first in research:
        if first["from"] not in selected or first["to"] in selected or first["relation"] != "derived_from":
            continue
        current, path, omitted, seen = first, [first], [], {first["from"]}
        while current["to"] not in selected:
            nid = current["to"]
            if nid in seen or by_id[nid].get("overview", {}).get("include", True):
                break
            seen.add(nid)
            if len(incoming.get(nid, [])) != 1 or len(outgoing.get(nid, [])) != 1:
                break
            following = outgoing[nid][0]
            if following["relation"] != "derived_from":
                break
            omitted.append(nid)
            path.append(following)
            current = following
        else:
            labels = list(dict.fromkeys(labelled(edge)["label"] for edge in path))
            via = "经省略节点 " if zh else "via omitted nodes "
            edges.append({"from": first["from"], "to": current["to"], "relation": "derived_from",
                          "label": "；".join(labels) + "（" + via + ", ".join(omitted) + "）",
                          "evidence": list(dict.fromkeys(value for edge in path for value in edge.get("evidence", []))),
                          "_via": omitted, "_change_label": "；".join(labels), "_bridge_label": labels[-1]})
    context = list(data.get("overview", {}).get("context", []))
    dependency_records = []
    resources = {}
    for edge in data["edges"]:
        if not edge.get("overview", {}).get("show", True):
            continue
        if edge["relation"] in ("uses_model", "uses_data") and edge["from"] in selected:
            resource, user = edge["to"], edge["from"]
        elif edge["relation"] == "produces" and (edge["from"] in selected or edge["to"] in selected):
            resource, user = edge["to"], edge["from"]
        else:
            continue
        dependency_records.append(edge)
        resources.setdefault((edge["relation"], resource), set()).add(user)
    labels = {"uses_model": "使用模型" if zh else "Model", "uses_data": "使用数据" if zh else "Data",
              "produces": "产出" if zh else "Output"}
    for (relation, nid), users in resources.items():
        target = by_id[nid]
        name = target.get("overview", {}).get("title") or target["title"]
        context.append(f"{labels[relation]}: {name} ({len(users)})")
    if len(nodes) > 1 and not edges:
        notices.append("所选节点之间没有可展示的研究关系；未推断连线，请补充有证据的边。" if zh else
                       "No displayable research edges among selected nodes; no connections inferred. Add evidenced edges.")
    if any(edge["from"] in selected and edge["to"] not in selected or
           edge["to"] in selected and edge["from"] not in selected for edge in research):
        notices.append("部分研究边的端点未入选；仅桥接显式省略且无分叉的派生单链，详见完整图。" if zh else
                       "Some research endpoints are outside this selection; only explicitly hidden unbranched derivations may bridge. See detailed map.")
    title = data.get("overview", {}).get("title") or (data["project"] + (" · 重要信息" if zh else " · Key experiments"))
    if group is not None:
        title += " · " + group
    return {**data, "nodes": nodes, "edges": edges, "_overview": {
        "title": title, "context": list(dict.fromkeys(context)), "notices": list(dict.fromkeys(notices)),
        "dependencies": dependency_records, "max_columns": data.get("overview", {}).get("max_columns", 3),
        "group": group, "missing": missing,
    }}


def markdown(data, language, r):
    """Keep complete overview fields and evidence beside the deliberately short cards."""
    cell, table, location = r["cell"], r["table"], r["location"]
    zh = language == "zh"
    meta = data["_overview"]
    output = ["# " + cell(meta["title"])]
    if meta["context"]:
        output.append(("共同上下文：\n\n" if zh else "Shared context:\n\n") +
                      "\n".join("- " + cell(value) for value in meta["context"]))
    output.append(table(["版本" if zh else "Version", "分组" if zh else "Group", "当前配置" if zh else "Config",
                         "Loss", "主要测量结果" if zh else "Measurements", "详情" if zh else "Details"], [
        [cell(n["_overview"]["title"]), cell(n["_overview"]["group"]),
         cell("\n".join(n["_overview"]["config"]) or meta["missing"]), cell(n["_overview"]["loss"]),
         cell(n["_overview"]["result"]), location(n["_overview"]["detail_path"])] for n in data["nodes"]]))
    output.append(table(["From → To", "Relation", "具体改动 / 比较" if zh else "Change / comparison", "Evidence"], [
        [cell(edge["from"] + " → " + edge["to"]), cell(edge["relation"]), cell(edge["label"]),
         cell(", ".join(edge.get("evidence", [])))] for edge in data["edges"]]))
    if meta["dependencies"]:
        output.append(("依赖上下文（不画连线）：" if zh else "Dependency context (no diagram arrows):") + "\n\n" +
                      table(["From → To", "Relation", "Label"], [
                          [cell(edge["from"] + " → " + edge["to"]), cell(edge["relation"]), cell(edge.get("label"))]
                          for edge in meta["dependencies"]]))
    if meta["notices"]:
        output.append(("整理说明：\n\n" if zh else "Curation notes:\n\n") +
                      "\n".join("- " + cell(value) for value in meta["notices"]))
    return "\n\n".join(output) + "\n"


def _short(value, width, font, lines, r, language):
    wrapped = r["_wrap_text"](value, width, font)
    parts = wrapped.split("\n")
    if len(parts) <= lines:
        return wrapped
    return "\n".join(parts[:max(0, lines - 1)] + [("… → 详情" if language == "zh" else "… → details")])


def excalidraw(data, existing, language, r, relayout=False, detail_path=None):
    """Render a bounded grid, keeping this view's manual elements and positions."""
    zh = language == "zh"
    meta = data["_overview"]
    old_elements = (existing or {}).get("elements", [])
    previous = r["_managed_lookup"]([element for element in old_elements
        if element.get("customData", {}).get("view") == "overview"])
    manual = [dict(element) for element in old_elements if not r["_managed"](element)]
    allocated = {element["id"] for element in manual}
    updated = int(time.time() * 1000)
    elements, cards = [], {}

    def allocate(kind, key):
        old = previous.get((kind, str(key)))
        base = old["id"] if old else r["_managed_id"]("overview-" + kind, str(key))
        candidate, suffix = base, 0
        while candidate in allocated:
            suffix += 1
            candidate = f"{base}-{suffix}"
        allocated.add(candidate)
        return candidate

    def panel(kind, key, content, x, y, width, font=FONT, color="#1e1e1e", fill="transparent", link=None,
              minimum_height=0, extra=None):
        old = previous.get((kind, key))
        old_text = previous.get(("text", key))
        old_custom = old.get("customData", {}) if old else {}
        manual_position = bool(old and (old_custom.get("layoutPlacement") == "manual" or
            old_custom.get("layoutPlacement") != "auto" or
            old["x"] != old_custom.get("autoX") or old["y"] != old_custom.get("autoY")))
        if old and not relayout and (manual_position or kind == "edge-label"):
            x, y = old["x"], old["y"]
        placement = ({"layoutPlacement": "manual"} if manual_position and not relayout else
                     {"layoutPlacement": "auto", "autoX": x, "autoY": y})
        pad_x, pad_y = (10, 8) if kind == "edge-label" else (20, 16)
        text = r["_wrap_text"](content, width - pad_x * 2, font)
        text_height = math.ceil(r["_line_count"](text) * font * 1.25 + 2)
        height = max(minimum_height, text_height + pad_y * 2)
        shape = r["_element_base"](allocate(kind, key), "rectangle", 0, updated)
        shape.update({"x": x, "y": y, "width": width, "height": height, "strokeColor": color if kind == "node" else "transparent",
                      "backgroundColor": fill, "strokeWidth": 2 if kind == "node" else 0,
                      "roughness": 0, "roundness": {"type": 3}, "link": r["_path_link"](link) if link else None,
                      "customData": r["_managed_data"](kind, key, view="overview", **{**placement, **(extra or {})})})
        shape = r["_preserved_shape"](shape, old, {"id", "type", "x", "y", "width", "height", "boundElements",
                                                                   "link", "customData", "updated", "isDeleted"})
        obj = r["_new_text_element"](allocate("text", key), key, text, x + pad_x, y + pad_y, width - pad_x * 2,
                                      text_height, font, color, 0, updated, shape["id"], old_text)
        # Compact cards have a readability floor; old detailed-view typography never leaks in.
        obj["fontSize"] = font
        obj["height"] = text_height
        obj["customData"]["view"] = "overview"
        shape["boundElements"] = [{"id": obj["id"], "type": "text"}]
        elements.extend((shape, obj))
        return shape

    grouped = {}
    for node in data["nodes"]:
        grouped.setdefault(node["_overview"]["group"], []).append(node)
    group_columns = {name: min(meta["max_columns"], math.ceil(math.sqrt(len(members))))
                     for name, members in grouped.items()}
    columns = max(group_columns.values(), default=1)
    canvas_width = columns * WIDTH + (columns - 1) * GAP_X
    header = _short(meta["title"], canvas_width - 40, FONT, 3, r, language)
    context = meta["context"]
    for value in context[:2]:
        header += "\n" + _short(value, canvas_width - 40, FONT, 2, r, language)
    legend = "实线：研究关系；虚线：对照" if zh else "Solid: research relation; dashed: comparison"
    header += "\n" + legend
    if len(data["nodes"]) > 1 and not data["edges"]:
        header += "\n" + ("未记录可展示的研究连线；请补充关系。" if zh else "No displayable research connections recorded.")
    top = panel("header", "overview-header", header, 80, 34, canvas_width, link=detail_path)
    y = top["y"] + top["height"] + (120 if meta["group"] is not None else 20)
    headings = [(top["x"], top["y"], top["x"] + top["width"], top["y"] + top["height"])]
    occupied = [r["_element_box"](element) for element in manual if not element.get("isDeleted")]
    if not relayout:
        occupied += [r["_element_box"](element) for (kind, _), element in previous.items() if kind == "node"]
    statuses = ({"planned": "待训练", "running": "运行中", "finished": "已完成", "failed": "失败",
                 "interrupted": "已中断", "archived": "已归档", "unknown": "状态未核实"} if zh else
                {"planned": "Planned", "running": "Running", "finished": "Finished", "failed": "Failed",
                 "interrupted": "Interrupted", "archived": "Archived", "unknown": "Status unverified"})
    for name, members in grouped.items():
        columns = group_columns[name]
        if meta["group"] is None:
            heading = panel("study", name, name, 80, y, canvas_width, font=24, color="#495057")
            headings.append(r["_element_box"](heading))
            y += heading["height"] + GAP_Y
        for row_index, offset in enumerate(range(0, len(members), columns)):
            row = members[offset:offset + columns]
            heights = []
            for column, node in enumerate(row):
                spec = node["_overview"]
                content = _short(spec["title"], WIDTH - 40, FONT, 3, r, language)
                content += "\n[" + statuses[node["execution_status"]] + "]"
                fields = [("配置" if zh else "Config", "；".join(spec["config"]) or meta["missing"], 4),
                          ("Loss", spec["loss"], 4), ("结果" if zh else "Result", spec["result"], 4)]
                for label, value, lines in fields:
                    content += "\n" + _short(f"{label}: {value}", WIDTH - 40, FONT, lines, r, language)
                slot = column if row_index % 2 == 0 else columns - column - 1
                x = 80 + slot * (WIDTH + GAP_X)
                key = node["id"]
                if ("node", key) not in previous or relayout:
                    # Manual notes occupy real space; a new card must not cover them.
                    wrapped = r["_wrap_text"](content, WIDTH - 40, FONT)
                    height = math.ceil(r["_line_count"](wrapped) * FONT * 1.25 + 2) + 32
                    while any(r["_overlaps"]((x - 18, y - 18, x + WIDTH + 18, y + height + 18), box) for box in occupied):
                        y += height + GAP_Y
                fill, stroke = r["STATUS_COLORS"][node["execution_status"]]
                shape = panel("node", key, content, x, y, WIDTH, color=stroke, fill=fill,
                              link=spec["detail_path"] or detail_path,
                              extra={"nodeId": key, "group": name})
                cards[key] = shape
                occupied.append(r["_element_box"](shape))
                heights.append(shape["y"] + shape["height"])
            y = max(heights) + GAP_Y
        y += 40 - GAP_Y
    if not data["nodes"]:
        panel("empty-state", "overview-empty", "没有入选节点。" if zh else "No selected experiments.", 80, y, WIDTH)

    # A gutter above each row carries horizontal edges and readable labels. Other
    # edges use the existing obstacle router, which can travel between grid rows.
    occurrence, pair_occurrence = {}, {}
    # Previous card boxes reserve space while placing new cards, but they are
    # no longer obstacles after reflow. Keeping them here displaces labels into
    # unrelated rows when a header or card becomes shorter.
    label_occupied = [r["_element_box"](shape) for shape in cards.values()] + headings + [
        r["_element_box"](element) for element in manual if not element.get("isDeleted")]
    bound = max(80 + canvas_width, max((shape["x"] + shape["width"] for shape in cards.values()), default=80))
    # Bound automatic label placement even for a very long lineage. Manual moves
    # intentionally remain the user's choice and can extend the canvas.
    label_occupied += [(-1e12, -1e12, 40, 1e12), (bound + 40, -1e12, 1e12, 1e12)]
    records = []
    for edge in data["edges"]:
        identity = (edge["from"], edge["relation"], edge["to"])
        count = occurrence.get(identity, 0)
        occurrence[identity] = count + 1
        key = json.dumps([*identity, count], ensure_ascii=False, separators=(",", ":"))
        records.append((edge, key))
        old_shape, old_text = previous.get(("edge-label", key)), previous.get(("text", key))
        if not relayout and r["_edge_label_is_manual"](old_shape, old_text):
            label_occupied.append(r["_element_box"](old_shape))
    arrows, labels = [], []
    for edge, key in records:
        source, target = cards[edge["from"]], cards[edge["to"]]
        pair = tuple(sorted((edge["from"], edge["to"])))
        lane = pair_occurrence.get(pair, 0)
        pair_occurrence[pair] = lane + 1
        same_row = abs(source["y"] - target["y"]) < 1
        if same_row:
            start = (source["x"] + WIDTH / 2, source["y"])
            end = (target["x"] + WIDTH / 2, target["y"])
            gutter_y = source["y"] - 65 - lane * 20
            route = [start, (start[0], gutter_y), (end[0], gutter_y), end]
            others = [r["_element_box"](shape) for shape in cards.values() if shape is not source and shape is not target]
            if any(r["_segment_intersects_box"](a, b, box) for a, b in zip(route, route[1:]) for box in others + headings):
                route = r["_route_edge"](start, end, source, target, cards, headings)
            sf = ef = 0
        else:
            start, end, sf, ef = r["_edge_points"](source, target, lane * 24)
            route = r["_route_edge"](start, end, source, target, cards, headings)
        arrow = r["_element_base"](allocate("edge", key), "arrow", 0, updated)
        arrow.update({"x": start[0], "y": start[1],
                      "width": max(p[0] for p in route) - min(p[0] for p in route),
                      "height": max(p[1] for p in route) - min(p[1] for p in route),
                      "points": [[p[0] - start[0], p[1] - start[1]] for p in route],
                      "strokeColor": "#495057", "strokeStyle": "dashed" if edge["relation"] == "compares_to" else "solid",
                      "roughness": 0, "startArrowhead": None, "endArrowhead": "arrow", "lastCommittedPoint": None,
                      "startBinding": {"elementId": source["id"], "focus": sf, "gap": 2},
                      "endBinding": {"elementId": target["id"], "focus": ef, "gap": 2},
                      "customData": r["_managed_data"]("edge", key, view="overview", relation=edge["relation"],
                                                        label=edge["label"], via=edge.get("_via", []), evidence=edge.get("evidence", []))})
        arrow = r["_preserved_shape"](arrow, previous.get(("edge", key)), {
            "id", "type", "x", "y", "width", "height", "points", "startBinding", "endBinding", "customData",
            "updated", "isDeleted", "strokeStyle", "startArrowhead", "endArrowhead"})
        for shape in (source, target):
            shape["boundElements"].append({"id": arrow["id"], "type": "arrow"})
        arrows.append(arrow)
        old_shape = previous.get(("edge-label", key)) if not relayout else None
        old_text = previous.get(("text", key))
        label_width = min(300, max(160, r["_text_width"](edge["label"], EDGE_FONT) / .88 + 24))
        names = {}
        for nid in (edge["from"], edge["to"]):
            title = next(node["_overview"]["title"] for node in data["nodes"] if node["id"] == nid)
            names[nid] = r["_excerpt"](title.split()[0] if title.split() else nid, 10)
        endpoints = names[edge["from"]] + "→" + names[edge["to"]]
        display_label = endpoints + " · " + edge["label"]
        if edge.get("_via"):
            display_label = endpoints + (f" · 经{len(edge['_via'])}个省略节点\n" if zh else f" · Via {len(edge['_via'])} omitted\n") + edge["_bridge_label"]
        label_width = min(300, max(label_width, r["_text_width"](display_label.split("\n")[0], EDGE_FONT) / .88 + 24))
        content = _short(display_label, label_width - 20, EDGE_FONT, 3, r, language)
        label_height = math.ceil(r["_line_count"](content) * EDGE_FONT * 1.25 + 2) + 16
        manual_label = r["_edge_label_is_manual"](old_shape, old_text)
        if manual_label:
            x, label_y = old_shape["x"], old_shape["y"]
        else:
            x, label_y = r["_edge_label_position"](label_width, label_height, route, label_occupied)
        # panel preserves all existing positions; labels preserve only manual ones.
        saved = previous.pop(("edge-label", key), None)
        if manual_label:
            previous[("edge-label", key)] = saved
        prior_count = len(elements)
        shape = panel("edge-label", key, content, x, label_y, label_width, font=EDGE_FONT,
                      color="#495057", fill="#ffffff", extra={"labelPlacement": "manual" if manual_label else "auto",
                                                                 **({} if manual_label else {"autoX": x, "autoY": label_y}),
                                                                 "fullLabel": edge["label"]})
        if saved:
            previous[("edge-label", key)] = saved
            # Preserve styling without overriding generated placement and readable geometry.
            shape.update({k: saved[k] for k in ("strokeColor", "backgroundColor", "opacity") if k in saved})
        labels.extend(elements[prior_count:])
        del elements[prior_count:]
        if not manual_label:
            label_occupied.append(r["_element_box"](shape))
    elements.extend(arrows + labels)

    old_ids = {element["id"] for element in old_elements if r["_managed"](element)}
    new_ids = {element["id"] for element in elements}
    shapes_by_id = {shape["id"]: shape for shape in cards.values()}
    for element in manual:
        for endpoint in ("startBinding", "endBinding"):
            binding = element.get(endpoint)
            if not isinstance(binding, dict):
                continue
            target = binding.get("elementId")
            if target in old_ids and target not in new_ids:
                element[endpoint] = None
            elif target in shapes_by_id:
                shapes_by_id[target]["boundElements"].append({"id": element["id"], "type": "arrow"})
        if element.get("type") == "text" and element.get("containerId") in old_ids:
            element["containerId"] = None
        if isinstance(element.get("boundElements"), list):
            element["boundElements"] = r["_binding_list"](binding for binding in element["boundElements"]
                if isinstance(binding, dict) and (binding.get("id") not in old_ids or binding.get("id") in new_ids))
    r["_preserve_unchanged_timestamps"](elements, previous)
    document = dict(existing or {})
    document.update({"type": "excalidraw", "version": 2, "source": (existing or {}).get("source", "https://excalidraw.com"),
                     "elements": elements + manual, "appState": (existing or {}).get("appState", {"viewBackgroundColor": "#ffffff", "gridSize": 20}),
                     "files": (existing or {}).get("files", {})})
    r["_validate_managed_bindings"](document)
    r["_valid_excalidraw"](document)
    return document
