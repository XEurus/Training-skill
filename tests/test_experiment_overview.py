"""Contracts for the curated compact view, independent of the detailed layout."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_experiment_map.py"
SPEC = importlib.util.spec_from_file_location("overview_renderer_test", SCRIPT)
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)


def node(nid, **extra):
    value = {"id": nid, "title": "Full title " + nid, "study": "Study", "execution_status": "finished"}
    value.update(extra)
    return value


def registry(nodes, edges=None, **extra):
    return {"schema_version": 1, "project": "Compact map", "updated_at": None,
            "nodes": nodes, "edges": edges or [], **extra}


def edge(a, b, relation="derived_from", **extra):
    return {"from": a, "to": b, "relation": relation, "overview": {"label": "BS4 → BS256; 10k → 50k"}, **extra}


def elements(doc, kind):
    return [e for e in doc["elements"] if e.get("customData", {}).get("kind") == kind]


def boxes(element):
    return (element["x"], element["y"], element["x"] + element["width"], element["y"] + element["height"])


def render(data, existing=None, **kwargs):
    r.validate(data)
    return r._render_overview_excalidraw(data, existing, **kwargs)


class OverviewTests(unittest.TestCase):
    def curated(self, n=9):
        return registry([node(str(i), overview={"title": f"V{i}", "group": "Research",
                       "config": ["Stage1 final hidden", "BS256; 50k updates"], "loss": "MSE + C + G + 10L",
                       "result": "ID / OOD 10.97 / 12.67 Å\nfinal50k; 64 frames/domain"}) for i in range(n)],
                        [edge(str(i), str(i + 1)) for i in range(n - 1)])

    def assert_geometry(self, doc):
        cards, labels = elements(doc, "node"), elements(doc, "edge-label")
        for text in elements(doc, "text"):
            minimum = 20 if text["containerId"] in {label["id"] for label in labels} else 22
            self.assertGreaterEqual(text["fontSize"], minimum)
            for line in text["text"].splitlines():
                self.assertLessEqual(r._text_width(line, text["fontSize"]), text["width"] * .88 + 1)
            self.assertLessEqual(r._line_count(text["text"]) * text["fontSize"] * text["lineHeight"], text["height"])
        for label in labels:
            for card in cards:
                self.assertFalse(r._overlaps(boxes(label), boxes(card)), (label["customData"], card["customData"]))
        for arrow in elements(doc, "edge"):
            points = [(arrow["x"] + p[0], arrow["y"] + p[1]) for p in arrow["points"]]
            for a, b in zip(points, points[1:]):
                for card in cards:
                    self.assertFalse(r._segment_intersects_box(a, b, boxes(card)), (arrow["customData"], card["customData"]))
        r._validate_managed_bindings(doc)

    def test_long_chain_wraps_with_readable_fonts_and_stable_ids(self):
        data = self.curated(22)
        original = copy.deepcopy(data)
        doc = render(data)
        self.assertEqual(data, original)
        self.assertEqual(len(elements(doc, "node")), 22)
        self.assertEqual(len({e["x"] for e in elements(doc, "node")}), 3)
        self.assertLess(max(r._element_box(e)[2] for e in doc["elements"]), 1800)
        self.assert_geometry(doc)
        self.assertEqual(r._serialize_excalidraw(doc), r._serialize_excalidraw(render(data, doc)))

    def test_four_cards_use_two_by_two_and_keep_status_and_measurement_scope(self):
        data = self.curated(4)
        data["nodes"][1]["execution_status"] = "running"
        data["nodes"][3]["execution_status"] = "interrupted"
        doc = render(data)
        cards = elements(doc, "node")
        self.assertEqual(len({e["x"] for e in cards}), 2)
        self.assertEqual(len({e["y"] for e in cards}), 2)
        text = "\n".join(e["text"] for e in elements(doc, "text"))
        self.assertIn("运行中", text)
        self.assertIn("已中断", text)
        self.assertIn("final50k", text)
        self.assertIn("64", text)
        self.assert_geometry(doc)

    def test_context_has_dependency_facts_without_dependency_arrows(self):
        data = self.curated(2)
        data["nodes"].append(node("data", overview={"include": False, "title": "Clean dataset"}))
        data["edges"] += [edge("0", "data", "uses_data"), edge("1", "data", "uses_data")]
        data["overview"] = {"context": ["A", "B", "C"], "max_columns": 3}
        prepared = r._overview_registry(data)
        self.assertEqual(len(prepared["edges"]), 1)
        self.assertTrue(any("Clean dataset (2)" in item for item in prepared["_overview"]["context"]))
        doc = render(data)
        self.assertEqual(len(elements(doc, "edge")), 1)
        header = next(e["text"] for e in elements(doc, "text") if e["customData"]["key"] == "overview-header")
        self.assertNotIn("Clean dataset", header)
        self.assertIn("Clean dataset", r.render_overview(data))
        self.assertIn("uses\\_data", r.render_overview(data))

    def test_fallback_does_not_mistake_summary_for_loss_or_infer_lineage(self):
        data = registry([node("v1", summary="Unrelated prose about loss", changes=["training setting"], results=["RMSD 3.2"]), node("v2")])
        prepared = r._overview_registry(data)
        self.assertEqual(prepared["edges"], [])
        self.assertIn("未整理", prepared["nodes"][0]["_overview"]["loss"])
        self.assertEqual(prepared["nodes"][0]["_overview"]["config"], [])
        self.assertEqual(prepared["nodes"][0]["_overview"]["result"], "RMSD 3.2")
        doc = render(data)
        text = "\n".join(e["text"] for e in elements(doc, "text"))
        self.assertNotIn("Unrelated prose", text)
        self.assertIn("未记录可展示", text)
        self.assertIn("未提供 overview", r.render_overview(data))

    def test_only_hidden_unbranched_derivation_is_bridged(self):
        data = registry([node("start"), node("hidden-machine-id-" * 10, overview={"include": False}), node("end")])
        hidden = data["nodes"][1]["id"]
        data["edges"] = [edge("start", hidden), edge(hidden, "end")]
        prepared = r._overview_registry(data)
        self.assertEqual(len(prepared["edges"]), 1)
        self.assertEqual(prepared["edges"][0]["_via"], [hidden])
        doc = render(data)
        text = "\n".join(e["text"] for e in elements(doc, "text"))
        self.assertIn("经1个省略节点", text)
        self.assertNotIn(hidden, text)
        self.assertIn(hidden, r.render_overview(data))
        for relation in ("compares_to", "continues_from", "merges_from"):
            data["edges"][1]["relation"] = relation
            self.assertEqual(r._overview_registry(data)["edges"], [])
        data["edges"][1]["relation"] = "derived_from"
        data["edges"][1]["overview"]["show"] = False
        self.assertEqual(r._overview_registry(data)["edges"], [])
        data["edges"][1]["overview"]["show"] = True
        data["nodes"].append(node("branch"))
        data["edges"].append(edge(hidden, "branch"))
        self.assertEqual(r._overview_registry(data)["edges"], [])

    def test_comparison_stays_comparison_and_suppressed_edge_stays_hidden(self):
        data = self.curated(3)
        data["edges"][0]["relation"] = "compares_to"
        data["edges"][1]["overview"]["show"] = False
        doc = render(data)
        arrows = elements(doc, "edge")
        self.assertEqual(len(arrows), 1)
        self.assertEqual(arrows[0]["strokeStyle"], "dashed")
        self.assertEqual(arrows[0]["customData"]["relation"], "compares_to")
        text = "\n".join(e["text"] for e in elements(doc, "text"))
        self.assertNotIn("研究派生", text)

    def test_overflow_keeps_complete_fields_in_markdown_and_link(self):
        data = self.curated(1)
        long = "非常长但有用的科学配置/测量结果" * 100
        data["nodes"][0]["overview"].update(config=[long], loss=long, result=long, detail_path="notes/v0.md")
        doc = render(data)
        body = next(e for e in elements(doc, "text") if e["customData"]["key"] == "0")
        self.assertIn("… → 详情", body["text"])
        self.assertLess(body["height"], 550)
        self.assertIn(long, r.render_overview(data))
        self.assertEqual(elements(doc, "node")[0]["link"], "notes/v0.md")
        self.assert_geometry(doc)

    def test_own_manual_layout_survives_but_detailed_geometry_is_not_imported(self):
        data = self.curated(2)
        detailed = r._render_excalidraw(data, None, "zh")
        for card in elements(detailed, "node"):
            card["x"] = 10000
        own = render(data, detailed)
        self.assertLess(max(e["x"] for e in elements(own, "node")), 1500)
        card = elements(own, "node")[0]
        card["x"], card["y"] = 50, 2000
        card["backgroundColor"] = "#abcdef"
        label = elements(own, "edge-label")[0]
        label["x"], label["y"] = 80, 1800
        manual = {"id": "manual-note", "type": "rectangle", "x": 80, "y": 2200,
                  "width": 300, "height": 90, "customData": {"author": "human"}}
        own["elements"].append(manual)
        own["appState"]["theme"] = "dark"
        own["files"] = {"file": {"dataURL": "preserved"}}
        refreshed = render(data, own)
        card2 = elements(refreshed, "node")[0]
        self.assertEqual((card2["x"], card2["y"], card2["backgroundColor"]), (50, 2000, "#abcdef"))
        label2 = elements(refreshed, "edge-label")[0]
        self.assertEqual((label2["x"], label2["y"]), (80, 1800))
        self.assertIn(manual, refreshed["elements"])
        self.assertEqual(refreshed["appState"], own["appState"])
        self.assertEqual(refreshed["files"], own["files"])
        self.assertEqual(r._serialize_excalidraw(refreshed), r._serialize_excalidraw(render(data, refreshed)))
        reset = render(data, refreshed, relayout=True)
        self.assertNotEqual(elements(reset, "node")[0]["y"], 2000)
        self.assertIn(manual, reset["elements"])

    def test_reflow_does_not_treat_previous_card_boxes_as_obstacles(self):
        data = self.curated(5)
        data["overview"] = {"max_columns": 2, "context": ["context " * 30]}
        before = render(data)
        data["overview"]["context"] = ["short"]
        refreshed, fresh = render(data, before), render(data)
        for actual, expected in zip(elements(refreshed, "edge-label"), elements(fresh, "edge-label")):
            self.assertEqual((actual["x"], actual["y"]), (expected["x"], expected["y"]))
        self.assert_geometry(refreshed)

    def test_overview_metadata_validation_is_strict_and_optional(self):
        data = self.curated(2)
        r.validate(data)
        bad = [("registry", {"max_columns": True}), ("registry", {"max_columns": 4}),
               ("registry", {"context": "text"}), ("node", {"config": "text"}),
               ("node", {"include": 1}), ("node", {"order": float("nan")}),
               ("node", {"loss": None}), ("edge", {"show": "true"}), ("edge", {"label": 1})]
        for kind, spec in bad:
            with self.subTest(kind=kind, spec=spec):
                changed = copy.deepcopy(data)
                target = changed if kind == "registry" else changed["nodes"][0] if kind == "node" else changed["edges"][0]
                target["overview"] = spec
                with self.assertRaises(ValueError):
                    r.validate(changed)

    def test_real_nine_card_fixture_layout(self):
        source = SCRIPT.parents[2] / "fixture" / "experiment-map.json"
        if not source.exists():
            self.skipTest("External evaluation fixture is not bundled with the skill")
        data = json.loads(source.read_text())
        prepared = r._overview_registry(data)
        self.assertEqual(len(prepared["nodes"]), 9)
        self.assertEqual(len(prepared["edges"]), 7)
        doc = render(data)
        self.assert_geometry(doc)
        self.assertLess(max(r._element_box(e)[2] for e in doc["elements"]), 1800)
        for group, count in (("坐标 FM", 5), ("潜空间 FM", 4)):
            grouped = render(data, group=group)
            self.assertEqual(len(elements(grouped, "node")), count)
            self.assert_geometry(grouped)
        text = "\n".join(e["text"] for e in elements(doc, "text"))
        self.assertIn("评估22k", text)
        self.assertIn("64帧/域", text)
        self.assertIn("经1个省略节点", text)
        bridge = next(e["text"] for e in elements(doc, "text") if "L1→L2" in e["text"])
        self.assertIn("BS256", bridge)
        self.assertIn("50k预算", bridge)
        self.assertIn("从零训练", bridge)
        self.assertNotIn("stage1_latent_fm_node13_2gpu_10k", bridge)


class OverviewCliTests(unittest.TestCase):
    def run_cli(self, source, *args):
        result = subprocess.run([sys.executable, str(SCRIPT), str(source), *map(str, args)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [Path(line) for line in result.stdout.splitlines()]

    def test_views_formats_group_isolation_and_noop_mtimes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "registry.json"
            data = registry([node("a", overview={"group": "组A"}), node("b", overview={"group": "组B"})], [edge("a", "b")])
            source.write_text(json.dumps(data))
            paths = self.run_cli(source)
            self.assertEqual({path.name for path in paths}, {"registry.md", "registry.excalidraw", "registry.overview.md", "registry.overview.excalidraw"})
            before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
            self.run_cli(source)
            self.assertEqual(before, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths})
            grouped = self.run_cli(source, "--overview-group", "组A")
            self.assertEqual(len(grouped), 2)
            self.assertTrue(all(".overview.group-" in path.name for path in grouped))
            self.assertEqual(before, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths})
            self.assertNotEqual(r._overview_output(root / "x.md", "组A"), r._overview_output(root / "x.md", "组B"))
            self.assertEqual(len(self.run_cli(source, "--view", "overview", "--format", "markdown")), 1)
            self.assertEqual(len(self.run_cli(source, "--view", "detailed", "--format", "excalidraw")), 1)
            custom = self.run_cli(source, "--view", "overview", "--format", "markdown", "--output", root / "custom.md")
            self.assertEqual(custom, [root / "custom.overview.md"])

    def test_invalid_overview_output_aborts_all_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "registry.json"
            source.write_text(json.dumps(registry([node("a")])))
            md = source.with_suffix(".md")
            md.write_text("preserved")
            source.with_name("registry.overview.excalidraw").write_text("broken")
            result = subprocess.run([sys.executable, str(SCRIPT), str(source)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(md.read_text(), "preserved")
            self.assertFalse(source.with_suffix(".excalidraw").exists())


if __name__ == "__main__":
    unittest.main()
