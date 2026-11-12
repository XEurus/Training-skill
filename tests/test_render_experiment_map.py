"""Rendering contracts for rich registries and safe incremental updates."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_experiment_map.py"
SPEC = importlib.util.spec_from_file_location("experiment_map_renderer", SCRIPT)
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


def node(nid, study="研究主线", **extra):
    value = {"id": nid, "title": "实验 " + nid, "study": study, "execution_status": "finished",
             "changes": ["清洗训练数据并固定评估口径"], "findings": [], "decision": None,
             "note_path": None, "revisions": [], "runs": [], "paths": []}
    value.update(extra)
    return value


def registry(nodes, edges=None):
    return {"schema_version": 1, "project": "Synthetic experiment provenance", "updated_at": "2026-11-03",
            "nodes": nodes, "edges": edges or []}


def managed(document, kind, key=None):
    values = [element for element in document["elements"]
              if element.get("customData", {}).get("managedBy") == renderer.MANAGED_BY
              and element["customData"].get("kind") == kind]
    return values if key is None else next(element for element in values if element["customData"]["key"] == key)


def render(data, existing=None, **kwargs):
    renderer.validate(data)
    return renderer._render_excalidraw(data, existing, "zh", **kwargs)


def boxes_overlap(left, right):
    return renderer._overlaps(renderer._element_box(left), renderer._element_box(right))


def connected_studies():
    """Twenty-two rich cards model a long route, two comparisons and external data."""
    ids = ["cache", "stage", "stage-clean", "pi", "prior-pair", "beta-pair", "clean-pair",
           "resume", "eval-large", "eval-small", "time-stop", "cache-alt",
           "time-beta", "time-uniform", "time-legacy", "clean-ablation",
           "data1", "data2", "data3", "archive1", "archive2", "archive3"]
    nodes = [node(nid, study=("stage" if nid in ("stage", "stage-clean", "resume") else
                             "prior" if nid in ("pi", "prior-pair", "beta-pair") else
                             "evaluation" if nid.startswith("eval-") else
                             "time" if nid.startswith("time-") else
                             "data" if nid.startswith("data") else nid),
                  changes=["固定训练与评估口径，比较不同的数据清洗策略", "保存配置、日志与模型来源"],
                  findings=["已记录 ID / OOD 对比结果"], note_path=f"notes/{nid}.md",
                  paths=[{"role": "output", "location": f"/synthetic/research/experiments/{nid}/output",
                          "storage": "external", "host": "cluster"}]) for nid in ids]
    edges = [{"from": source, "to": target, "relation": "derived_from"}
             for source, target in zip(ids[:6], ids[1:7])]
    edges += [{"from": "stage-clean", "to": "resume", "relation": "continues_from"}]
    edges += [{"from": "pi", "to": target, "relation": "compares_to"} for target in ("eval-large", "eval-small")]
    edges += [{"from": "time-beta", "to": target, "relation": "compares_to"} for target in ("time-uniform", "time-legacy")]
    edges += [{"from": source, "to": target, "relation": "derived_from"} for source, target in
              (("time-beta", "clean-ablation"), ("data1", "data2"), ("data2", "data3"),
               ("data3", "clean-ablation"), ("data3", "clean-pair"))]
    return registry(nodes, edges)


class RichMapTests(unittest.TestCase):
    def rich_node(self):
        return node("model", summary="测试长度分布改变时的训练表现", question="是否能改善长链重建？",
                    results=["ID RMSD 2.1 Å", "OOD RMSD 3.2 Å", "成功率 76%", "第四项完整保留在索引", "第五项完整保留在索引"],
                    findings=["冻结缓存后改善吞吐"], decision="继续固定基线比较",
                    note_path="notes/长链实验.md",
                    revisions=[{"id": "code-1", "branch": "codex/very-long-research-branch-for-reconstruction-and-caching",
                                "commit": "abc123456789012345", "observed_at": "2026-11-01"}],
                    executions=[{"id": "local-20261103-seed7", "backend": "local", "status": "interrupted",
                                 "directory": "/research/many/nested/directories/checkpoints/seed7", "host": "cluster",
                                 "observed_at": "2026-11-03T12:00:00Z", "revision_id": "code-1"}],
                    paths=[{"role": "checkpoint", "location": "/research/many/nested/directories/checkpoints/best.pt",
                            "host": "cluster", "storage": "external"}],
                    display={"primary_path": "checkpoint"})

    def test_rich_content_links_and_complete_markdown(self):
        rich = self.rich_node()
        data = registry([rich])
        document = render(data)
        body = managed(document, "text", "model:body")["text"]
        for value in ("ID RMSD", "OOD RMSD", "冻结缓存", "继续固定", "abc1234567", "local-20261103-seed7", "2026-11-03T12:00:00Z"):
            self.assertIn(value, body)
        links = managed(document, "node-link")
        self.assertEqual(len(links), 3)
        self.assertFalse(any((link["link"] or "").startswith("sftp://cluster/") for link in links))
        self.assertTrue(any(link["link"] == "notes/%E9%95%BF%E9%93%BE%E5%AE%9E%E9%AA%8C.md" for link in links))
        texts = {element["containerId"]: element for element in managed(document, "text")}
        for link in links:
            self.assertNotIn("/research/many/nested", texts[link["id"]]["text"])
        self.assertTrue(any("[cluster]" in texts[link["id"]]["text"] for link in links))
        markdown = renderer.render(data, "zh")
        for value in ("第四项完整保留在索引", "第五项完整保留在索引", rich["executions"][0]["directory"],
                      rich["paths"][0]["location"], "abc123456789012345"):
            self.assertIn(value, markdown)
        renderer._validate_managed_bindings(document)

    def test_topology_groups_and_rich_cards_do_not_overlap(self):
        nodes = [self.rich_node(), node("branch-a", results=["结果一", "结果二", "结果三"]),
                 node("branch-b", results=["长链重建度量 " * 15] * 5), node("other", study="独立课题")]
        data = registry(nodes, [{"from": "model", "to": "branch-a", "relation": "derived_from"},
                                {"from": "model", "to": "branch-b", "relation": "derived_from"}])
        document = render(data)
        shapes = managed(document, "node")
        baseline = managed(document, "node", "model")
        self.assertLess(baseline["x"], managed(document, "node", "branch-a")["x"])
        self.assertEqual(managed(document, "node", "branch-a")["x"], managed(document, "node", "branch-b")["x"])
        for index, shape in enumerate(shapes):
            for other in shapes[index + 1:]:
                self.assertFalse(boxes_overlap(shape, other))
        for text in managed(document, "text"):
            for line in text["text"].splitlines():
                self.assertLessEqual(renderer._text_width(line, text["fontSize"]), text["width"] * 0.88 + 1)
            self.assertLessEqual(renderer._line_count(text["text"]) * text["fontSize"] * text["lineHeight"], text["height"] + 1)

    def test_dependency_direction_evidence_and_readable_labels(self):
        data = registry([node("consumer"), node("cache", study="基础缓存"), node("artifact")], [
            {"from": "consumer", "to": "cache", "relation": "uses_model", "label": "冻结 Stage1 缓存", "evidence": ["ev-cache"]},
            {"from": "consumer", "to": "artifact", "relation": "produces"}])
        document = render(data)
        self.assertLess(managed(document, "node", "cache")["x"], managed(document, "node", "consumer")["x"])
        self.assertLess(managed(document, "node", "consumer")["x"], managed(document, "node", "artifact")["x"])
        arrow = managed(document, "edge")[0]
        self.assertEqual(arrow["startBinding"]["elementId"], managed(document, "node", "consumer")["id"])
        self.assertEqual(arrow["endBinding"]["elementId"], managed(document, "node", "cache")["id"])
        self.assertEqual(arrow["strokeStyle"], "dashed")
        self.assertEqual(arrow["customData"]["evidence"], ["ev-cache"])
        label = managed(document, "text", '["consumer","uses_model","cache",0]')
        self.assertIn("使用模型", label["text"])
        self.assertIn("冻结 Stage1 缓存", label["text"])
        self.assertGreaterEqual(managed(document, "edge-label")[0]["width"], 160)
        markdown = renderer.render(data, "zh")
        self.assertIn("ev-cache", markdown)
        self.assertIn("uses\\_model", markdown)

    def test_orthogonal_routes_avoid_non_endpoint_cards_and_labels_are_clear(self):
        nodes = [self.rich_node(), node("branch-a"), node("branch-b"),
                 node("cache", study="缓存"), node("data", study="缓存")]
        data = registry(nodes, [
            {"from": "model", "to": "branch-a", "relation": "derived_from", "label": "时间采样对照"},
            {"from": "model", "to": "branch-b", "relation": "derived_from"},
            {"from": "model", "to": "cache", "relation": "uses_model", "label": "冻结 Stage1 特征"},
            {"from": "model", "to": "data", "relation": "uses_data", "label": "SBM20 v3"}])
        scenarios = [data, registry([
            node("source", display={"x": 80, "y": 400}),
            node("target", display={"x": 1680, "y": 400}),
            node("obstacle", changes=["多行内容 " * 25] * 3, display={"x": 880, "y": 300})],
            [{"from": "source", "to": "target", "relation": "derived_from"}])]
        for scenario in scenarios:
            document = render(scenario)
            shapes = managed(document, "node")
            for arrow in managed(document, "edge"):
                endpoints = {arrow["startBinding"]["elementId"], arrow["endBinding"]["elementId"]}
                points = [(arrow["x"] + point[0], arrow["y"] + point[1]) for point in arrow["points"]]
                for start, end in zip(points, points[1:]):
                    self.assertTrue(start[0] == end[0] or start[1] == end[1])
                    for shape in shapes:
                        if shape["id"] not in endpoints:
                            self.assertFalse(renderer._segment_intersects_box(start, end,
                                             (shape["x"], shape["y"], shape["x"] + shape["width"], shape["y"] + shape["height"])),
                                             f"{arrow['customData']['key']} crosses {shape['customData']['key']}")
            for label in managed(document, "edge-label"):
                raw_box = (label["x"], label["y"], label["x"] + label["width"], label["y"] + label["height"])
                for shape in shapes:
                    self.assertFalse(renderer._overlaps(raw_box, renderer._element_box(shape)))

    def test_noop_and_saved_geometry_survive_and_explicit_relayout_moves(self):
        data = registry([self.rich_node(), node("branch")], [{"from": "model", "to": "branch", "relation": "derived_from"}])
        first = render(data)
        self.assertEqual(first, render(data, first))
        modified = copy.deepcopy(first)
        shape = managed(modified, "node", "model")
        shape["x"], shape["y"], shape["backgroundColor"] = 3150, 480, "#123456"
        label = managed(modified, "edge-label")[0]
        label["x"], label["y"] = 2600, 420
        manual = {**renderer._element_base("manual", "text", "x", 1), "x": 8000, "y": 100,
                  "width": 120, "height": 40, "text": "人工批注"}
        modified["elements"].append(manual)
        refreshed = render(data, modified)
        self.assertEqual((managed(refreshed, "node", "model")["x"], managed(refreshed, "node", "model")["y"]), (3150, 480))
        self.assertEqual(managed(refreshed, "node", "model")["backgroundColor"], "#123456")
        self.assertEqual((managed(refreshed, "edge-label")[0]["x"], managed(refreshed, "edge-label")[0]["y"]), (2600, 420))
        self.assertIn(manual, refreshed["elements"])
        rearranged = render(data, modified, relayout=True)
        self.assertNotEqual(managed(rearranged, "node", "model")["x"], 3150)
        self.assertIn(manual, rearranged["elements"])
        self.assertEqual({element["id"] for element in first["elements"]},
                         {element["id"] for element in rearranged["elements"]} - {"manual"})

    def test_optional_display_layout_hints_and_cycle(self):
        data = registry([node("b", display={"group": "组", "order": 2, "width": 560}),
                         node("a", display={"group": "组", "order": 1}),
                         node("pinned", display={"x": 2500, "y": 300, "order": None})], [
            {"from": "a", "to": "b", "relation": "derived_from"},
            {"from": "b", "to": "a", "relation": "continues_from"}])
        document = render(data)
        self.assertEqual(managed(document, "node", "b")["width"], 560)
        self.assertLess(managed(document, "node", "a")["y"], managed(document, "node", "b")["y"])
        self.assertEqual((managed(document, "node", "pinned")["x"], managed(document, "node", "pinned")["y"]), (2500, 300))

    def test_independent_studies_pack_into_compact_blocks(self):
        document = render(registry([node(f"n{index}", study=f"课题{index}") for index in range(6)]))
        shapes = managed(document, "node")
        self.assertGreater(len({shape["x"] for shape in shapes}), 1)
        for index, shape in enumerate(shapes):
            for other in shapes[index + 1:]:
                self.assertFalse(boxes_overlap(shape, other))

    def test_connected_study_stress_layout_and_native_arrow_contract(self):
        data = connected_studies()
        document = render(data)
        shapes = managed(document, "node")
        main = [managed(document, "node", nid) for nid in ("cache", "stage", "stage-clean", "pi", "prior-pair", "beta-pair", "clean-pair")]
        centers = [shape["y"] + shape["height"] / 2 for shape in main]
        self.assertLess(max(centers) - min(centers), max(shape["height"] for shape in main))
        self.assertLess(managed(document, "node", "pi")["x"], managed(document, "node", "eval-large")["x"])
        width = max(shape["x"] + shape["width"] for shape in shapes) - min(shape["x"] for shape in shapes)
        height = max(shape["y"] + shape["height"] for shape in shapes) - min(shape["y"] for shape in shapes)
        self.assertGreater(sum(shape["width"] * shape["height"] for shape in shapes) / (width * height), 0.35)
        for arrow in managed(document, "edge"):
            # Native Excalidraw smooths multi-point arrows into huge curves if this is type 2.
            self.assertIsNone(arrow["roundness"])
            endpoints = {arrow["startBinding"]["elementId"], arrow["endBinding"]["elementId"]}
            points = [(arrow["x"] + point[0], arrow["y"] + point[1]) for point in arrow["points"]]
            for start, end in zip(points, points[1:]):
                for shape in shapes:
                    if shape["id"] not in endpoints:
                        self.assertFalse(renderer._segment_intersects_box(start, end,
                                         (shape["x"], shape["y"], shape["x"] + shape["width"], shape["y"] + shape["height"])))
        right = max(shape["x"] + shape["width"] for shape in shapes)
        for label in managed(document, "edge-label"):
            self.assertLessEqual(label["x"] + label["width"], right + 40)
        modified = copy.deepcopy(document)
        for arrow in managed(modified, "edge"):
            arrow["roundness"] = {"type": 2}
        moved = managed(modified, "node", "cache")
        moved["x"] -= 120
        migrated = render(data, modified)
        self.assertEqual(managed(migrated, "node", "cache")["x"], moved["x"])
        self.assertTrue(all(arrow["roundness"] is None for arrow in managed(migrated, "edge")))

    def test_obstructed_label_stays_near_its_route(self):
        x, y = renderer._edge_label_position(160, 38, [(0, 0), (0, 200)],
                                              [(-100, -20, 100, 220), (10000, 0, 10500, 300)])
        self.assertLess(abs(x), 300)
        self.assertFalse(renderer._overlaps((x, y, x + 160, y + 38), (-100, -20, 100, 220)))

    def test_label_can_touch_its_route_without_covering_a_heading(self):
        x, y = renderer._edge_label_position(160, 38, [(0, 0), (300, 0)], [(-50, 0, 350, 50)])
        self.assertEqual(y + 38, 0)
        self.assertEqual(renderer._label_route_distance((x, y, x + 160, y + 38), [(0, 0), (300, 0)]), 0)

    def test_longer_relation_label_grows_without_covering_cards(self):
        data = registry([node("baseline"), node("variant")],
                        [{"from": "baseline", "to": "variant", "relation": "compares_to", "label": "短"}])
        planned = render(data)
        old_label = managed(planned, "edge-label")[0]
        data["edges"][0]["label"] = "指标与评估集发生变化，" * 24
        updated = render(data, planned)
        label = managed(updated, "edge-label")[0]
        text = next(element for element in updated["elements"] if element.get("containerId") == label["id"])
        self.assertGreater(label["height"], old_label["height"])
        self.assertLessEqual(text["y"] + text["height"], label["y"] + label["height"])
        label_box = (label["x"], label["y"], label["x"] + label["width"], label["y"] + label["height"])
        for card in managed(updated, "node"):
            self.assertFalse(renderer._overlaps(label_box, renderer._element_box(card)))
        self.assertEqual(renderer._serialize_excalidraw(updated), renderer._serialize_excalidraw(render(data, updated)))

    def test_legacy_label_moved_without_updating_version_is_preserved(self):
        data = registry([node("baseline"), node("variant")],
                        [{"from": "baseline", "to": "variant", "relation": "compares_to"}])
        document = render(data)
        label = managed(document, "edge-label")[0]
        for key in ("labelPlacement", "autoX", "autoY"):
            label["customData"].pop(key)
        card = managed(document, "node", "baseline")
        label["x"], label["y"] = card["x"] + 30, card["y"] + 30
        updated = render(data, document)
        saved = managed(updated, "edge-label")[0]
        self.assertEqual((saved["x"], saved["y"]), (label["x"], label["y"]))
        self.assertEqual(saved["customData"]["labelPlacement"], "manual")

    def test_auto_label_moves_away_from_unmanaged_annotation(self):
        data = registry([node("baseline"), node("variant")],
                        [{"from": "baseline", "to": "variant", "relation": "compares_to"}])
        document = render(data)
        label = managed(document, "edge-label")[0]
        annotation = renderer._element_base("manual-note", "rectangle", "a999", 1)
        annotation.update({"x": label["x"], "y": label["y"], "width": label["width"], "height": label["height"]})
        document["elements"].append(annotation)
        updated = render(data, document)
        relocated = managed(updated, "edge-label")[0]
        self.assertIn(annotation, updated["elements"])
        self.assertNotEqual((relocated["x"], relocated["y"]), (label["x"], label["y"]))
        self.assertFalse(boxes_overlap(relocated, annotation))
        self.assertEqual(renderer._serialize_excalidraw(updated), renderer._serialize_excalidraw(render(data, updated)))

    def test_touching_manually_moved_nodes_do_not_break_incremental_labels(self):
        data = registry([node("left"), node("right")],
                        [{"from": "left", "to": "right", "relation": "compares_to"}])
        document = render(data)
        left = managed(document, "node", "left")
        right = managed(document, "node", "right")
        right["x"], right["y"] = left["x"] + left["width"], left["y"]
        updated = render(data, document)
        saved = managed(updated, "node", "right")
        self.assertEqual((saved["x"], saved["y"]), (right["x"], right["y"]))
        self.assertGreaterEqual(len(managed(updated, "edge")[0]["points"]), 2)
        label = managed(updated, "edge-label")[0]
        label_box = (label["x"], label["y"], label["x"] + label["width"], label["y"] + label["height"])
        for card in managed(updated, "node"):
            self.assertFalse(renderer._overlaps(label_box, renderer._element_box(card)))
        self.assertEqual(renderer._serialize_excalidraw(updated), renderer._serialize_excalidraw(render(data, updated)))

    def test_routes_avoid_study_headings(self):
        document = render(connected_studies())
        headings = managed(document, "study")
        for arrow in managed(document, "edge"):
            points = [(arrow["x"] + x, arrow["y"] + y) for x, y in arrow["points"]]
            for start, end in zip(points, points[1:]):
                for heading in headings:
                    self.assertFalse(renderer._segment_intersects_box(start, end, renderer._element_box(heading)),
                                     (arrow["id"], heading["id"]))

    def test_explicit_node_position_keeps_new_heading_above_the_card(self):
        document = render(registry([node("baseline", display={"x": 820, "y": 210})]))
        card = managed(document, "node", "baseline")
        heading = managed(document, "study")[0]
        self.assertEqual(heading["x"], card["x"])
        self.assertLess(heading["y"] + heading["height"], card["y"])

    def test_relation_labels_render_above_all_managed_arrows(self):
        document = render(connected_studies())
        elements = document["elements"]
        arrow_positions = [position for position, element in enumerate(elements)
                           if element.get("customData", {}).get("kind") == "edge"]
        label_positions = [position for position, element in enumerate(elements)
                           if element.get("customData", {}).get("kind") == "edge-label"]
        self.assertLess(max(arrow_positions), min(label_positions))

    def test_focus_keeps_recursive_dependencies_and_complete_index(self):
        data = registry([node("experiment", study="目标"), node("cache", study="基础"),
                         node("data", study="基础"), node("unrelated", study="其他")], [
            {"from": "experiment", "to": "cache", "relation": "uses_model"},
            {"from": "cache", "to": "data", "relation": "uses_data"}])
        original = copy.deepcopy(data)
        focused = renderer._focus_registry(data, ["目标"], [])
        self.assertEqual({n["id"] for n in focused["nodes"]}, {"experiment", "cache", "data"})
        self.assertEqual(set(focused["_focus"]["context_ids"]), {"cache", "data"})
        self.assertEqual(data, original)
        self.assertIn("unrelated", renderer.render(data, "zh", focused))
        self.assertIn("依赖上下文", managed(render(focused), "text", "cache:body")["text"])
        with tempfile.TemporaryDirectory(prefix="map-focus-test-") as temporary:
            source = Path(temporary) / "registry.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            overview = source.with_suffix(".excalidraw")
            overview.write_text("sentinel", encoding="utf-8")
            completed = subprocess.run([sys.executable, str(SCRIPT), str(source), "--study", "目标"], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(overview.read_text(), "sentinel")
            focused_outputs = list(Path(temporary).glob("registry.focus-*.excalidraw"))
            self.assertEqual(len([path for path in focused_outputs if ".overview." not in path.name]), 1)
            self.assertEqual(len([path for path in focused_outputs if ".overview." in path.name]), 1)
            completed = subprocess.run([sys.executable, str(SCRIPT), str(source), "--node", "missing"], capture_output=True, text=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Unknown focus node", completed.stderr)

    def test_invalid_execution_revision_or_duplicate_is_rejected(self):
        data = registry([node("a", executions=[{"id": "run", "revision_id": "missing"}])])
        with self.assertRaisesRegex(ValueError, "references missing revision"):
            renderer.validate(data)
        data["nodes"][0]["executions"] = [{"id": "run"}, {"id": "run"}]
        with self.assertRaisesRegex(ValueError, "Duplicate or empty execution"):
            renderer.validate(data)


if __name__ == "__main__":
    unittest.main()
