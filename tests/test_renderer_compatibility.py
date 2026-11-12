import json
import importlib.util
import hashlib
import os
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'render_experiment_map.py'
MANAGED = 'mlflow-experiment-journal'
spec = importlib.util.spec_from_file_location('renderer', SCRIPT)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def node(node_id, status='finished', changes=None, revisions=None, title=None):
    return {
        'id': node_id,
        'title': title or f'{node_id} title',
        'study': 'fictional study',
        'execution_status': status,
        'changes': changes or ['synthetic baseline'],
        'findings': [],
        'decision': None,
        'note_path': None,
        'revisions': revisions or [{
            'id': 'revision-1', 'repo': 'fictional-repo', 'branch': 'main', 'commit': 'a1b2c3',
            'worktree': None, 'host': None, 'observed_at': None, 'code_snapshot': None,
            'patch_path': None, 'dirty': False,
        }],
        'runs': [],
        'paths': [],
    }


def registry(nodes=None, edges=None):
    return {'schema_version': 1, 'project': 'Fictional Foldscape Study', 'updated_at': '2026-11-03',
            'nodes': nodes if nodes is not None else [
                node('exp-a', changes=['baseline fit']),
                node('exp-b', status='unknown', changes=['historical branch comparison'], revisions=[
                    {'id': 'old', 'repo': 'fictional-repo', 'branch': 'legacy', 'commit': '111111',
                     'worktree': None, 'host': None, 'observed_at': '2025-10-01', 'code_snapshot': None,
                     'patch_path': None, 'dirty': False},
                    {'id': 'new', 'repo': 'fictional-repo', 'branch': 'main', 'commit': '222222',
                     'worktree': None, 'host': None, 'observed_at': '2026-11-03', 'code_snapshot': None,
                     'patch_path': None, 'dirty': False},
                ]),
            ],
            'edges': edges if edges is not None else [{'from': 'exp-a', 'to': 'exp-b', 'relation': 'derived_from'}]}


def call(registry_path, *args):
    return subprocess.run(['python', str(SCRIPT), str(registry_path), *map(str, args)], text=True, capture_output=True)


def managed(document, kind=None):
    return [element for element in document['elements']
            if element.get('customData', {}).get('managedBy') == MANAGED
            and (kind is None or element['customData'].get('kind') == kind)]


def by_key(document, kind, key):
    return next(element for element in managed(document, kind) if element['customData']['key'] == key)


def overlaps(a, b, padding=0):
    return a['x'] - padding < b['x'] + b['width'] and b['x'] - padding < a['x'] + a['width'] and \
        a['y'] - padding < b['y'] + b['height'] and b['y'] - padding < a['y'] + a['height']


def record_run_and_results(experiment):
    experiment['execution_status'] = 'running'
    experiment['runs'] = [{
        'run_id': f"synthetic-run-{experiment['id']}",
        'tracking_uri': 'file:///tmp/synthetic-mlruns',
        'revision_id': 'revision-1',
        'status': 'running',
    }]
    experiment['results'] = [f'long synthetic result {index}: ' + 'value and analysis ' * 9
                             for index in range(3)]
    experiment['paths'] = [
        {'role': 'output', 'location': '/tmp/synthetic-output/results', 'storage': 'external'},
        {'role': 'checkpoint', 'location': '/tmp/synthetic-output/best.pt', 'storage': 'external'},
    ]


def label_route_distance(label, arrow):
    points = [(arrow['x'] + point[0], arrow['y'] + point[1]) for point in arrow['points']]
    if len(points) < 2:
        raise AssertionError('arrow must have at least one segment')
    distances = []
    for start, end in zip(points, points[1:]):
        if start[0] != end[0] and start[1] != end[1]:
            raise AssertionError('expected an orthogonal route')
        horizontal = max(0, min(start[0], end[0]) - label['x'] - label['width'],
                         label['x'] - max(start[0], end[0]))
        vertical = max(0, min(start[1], end[1]) - label['y'] - label['height'],
                       label['y'] - max(start[1], end[1]))
        distances.append(horizontal + vertical)
    return min(distances)


class RendererCliTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('EXPERIMENT_JOURNAL_NATIVE_RUNTIME'),
                         'Set EXPERIMENT_JOURNAL_NATIVE_RUNTIME for native Excalidraw regression')
    def test_native_export_with_manual_elements_and_legacy_generated_indices(self):
        preview = SCRIPT.with_name('preview_experiment_map.mjs')
        for manual_index in (None, 'a0'):
            with self.subTest(manual_index=manual_index):
                self.assert_cli_success(self.registry_path)
                path = self.registry_path.with_suffix('.excalidraw')
                document = json.loads(path.read_text(encoding='utf-8'))
                # Reproduce the old generator's invalid index format, followed
                # by an ordinary manual element with or without a native key.
                for number, element in enumerate(document['elements'], 1):
                    if element.get('customData', {}).get('managedBy') == MANAGED:
                        element['index'] = f'z{number:08d}'
                manual = {
                    'id': 'native-manual-note', 'type': 'rectangle', 'x': 1800, 'y': 400,
                    'width': 150, 'height': 80, 'angle': 0, 'strokeColor': '#7048e8',
                    'backgroundColor': '#f3f0ff', 'fillStyle': 'solid', 'strokeWidth': 2,
                    'strokeStyle': 'solid', 'roughness': 0, 'opacity': 100, 'groupIds': [],
                    'frameId': None, 'roundness': None, 'seed': 42, 'version': 1,
                    'versionNonce': 42, 'isDeleted': False, 'boundElements': None,
                    'updated': 1, 'link': None, 'locked': False,
                }
                if manual_index is not None:
                    manual['index'] = manual_index
                document['elements'] = [e for e in document['elements'] if e['id'] != manual['id']] + [manual]
                path.write_text(json.dumps(document), encoding='utf-8')
                self.assert_cli_success(self.registry_path)
                refreshed = json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(next(e for e in refreshed['elements'] if e['id'] == manual['id']), manual)
                self.assert_outputs_unchanged_on_repeat(self.registry_path)
                output = self.root / ('native-' + str(manual_index))
                command = ['node', str(preview), str(path), str(output), '--runtime-dir',
                           os.environ['EXPERIMENT_JOURNAL_NATIVE_RUNTIME']]
                browser = os.environ.get('EXPERIMENT_JOURNAL_NATIVE_BROWSER')
                if browser:
                    command += ['--browser', browser]
                environment = os.environ.copy()
                long_temp = None
                if manual_index is not None and Path('/proc/self/fd').is_dir():
                    long_temp = self.root / ('isolated-native-preview-' + 'x' * 110)
                    long_temp.mkdir()
                    environment['TMPDIR'] = str(long_temp)
                result = subprocess.run(command, capture_output=True, text=True, timeout=90,
                                        env=environment)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads((output / 'render.json').read_text())['errors'], [])
                self.assertTrue((output / 'native.svg').stat().st_size > 100)
                if long_temp is not None:
                    self.assertEqual(list(long_temp.iterdir()), [])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='experiment-map-test-', dir='/tmp')
        self.root = Path(self.temp.name)
        self.registry_path = self.root / 'registry.json'
        self.registry_path.write_text(json.dumps(registry(), ensure_ascii=False), encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def assert_cli_success(self, registry_path):
        result = call(registry_path)
        self.assertEqual(result.returncode, 0, result.stderr)

    def assert_outputs_unchanged_on_repeat(self, registry_path):
        paths = [registry_path.with_suffix('.md'), registry_path.with_suffix('.excalidraw')]
        before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths]
        time.sleep(0.02)
        self.assert_cli_success(registry_path)
        self.assertEqual(before, [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths])

    def assert_auto_labels_clear_cards(self, document):
        cards = managed(document, 'node')
        for label in managed(document, 'edge-label'):
            if label['customData'].get('labelPlacement') != 'auto':
                continue
            self.assertEqual((label['customData']['autoX'], label['customData']['autoY']),
                             (label['x'], label['y']))
            for card in cards:
                self.assertFalse(overlaps(label, card),
                                 f"automatic label {label['id']} overlaps card {card['id']}")

    def test_growth_moves_obstructed_auto_labels_including_legacy_ones(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                root = self.root / ('legacy' if legacy else 'current')
                root.mkdir()
                registry_path = root / 'registry.json'
                diagram_path = registry_path.with_suffix('.excalidraw')
                experiments = [node('source', status='planned'), node('target', status='planned'),
                               node('growing', status='planned')]
                for experiment, position in zip(experiments, ((80, 800), (1700, 800), (950, 650))):
                    experiment['display'] = {'x': position[0], 'y': position[1]}
                data = registry(nodes=experiments, edges=[
                    {'from': 'source', 'to': 'target', 'relation': 'derived_from'},
                ])
                registry_path.write_text(json.dumps(data), encoding='utf-8')
                self.assert_cli_success(registry_path)
                planned = json.loads(diagram_path.read_text(encoding='utf-8'))
                label = managed(planned, 'edge-label')[0]
                self.assertEqual(label['customData']['labelPlacement'], 'auto')
                if legacy:
                    for field in ('labelPlacement', 'autoX', 'autoY'):
                        label['customData'].pop(field)
                    digest = hashlib.sha256(label['id'].encode('utf-8')).hexdigest()
                    self.assertEqual(label['version'], 1)
                    self.assertEqual(label['seed'], int(digest[:8], 16) & 0x7fffffff)
                    self.assertEqual(label['versionNonce'], int(digest[8:16], 16) & 0x7fffffff)
                old_label = dict(label)
                moved_card = by_key(planned, 'node', 'growing')
                moved_card['x'] += 10
                moved_card['version'] += 1
                saved_position = (moved_card['x'], moved_card['y'])
                initial_height = moved_card['height']
                self.assertFalse(overlaps(old_label, moved_card))
                note = {
                    'id': 'human-annotation', 'type': 'rectangle', 'x': 4000, 'y': 400,
                    'width': 150, 'height': 80, 'angle': 0, 'strokeColor': '#7048e8',
                    'backgroundColor': '#f3f0ff', 'fillStyle': 'solid', 'strokeWidth': 2,
                    'strokeStyle': 'solid', 'roughness': 0, 'opacity': 100, 'groupIds': [],
                    'frameId': None, 'index': 'a999', 'roundness': {'type': 3}, 'seed': 42,
                    'version': 1, 'versionNonce': 42, 'isDeleted': False, 'boundElements': None,
                    'updated': 1, 'link': None, 'locked': False, 'customData': {'author': 'human'},
                }
                planned['elements'].append(note)
                diagram_path.write_text(json.dumps(planned), encoding='utf-8')

                record_run_and_results(experiments[-1])
                registry_path.write_text(json.dumps(data), encoding='utf-8')
                self.assert_cli_success(registry_path)
                refreshed = json.loads(diagram_path.read_text(encoding='utf-8'))
                grown_card = by_key(refreshed, 'node', 'growing')
                new_label = managed(refreshed, 'edge-label')[0]
                self.assertGreater(grown_card['height'], initial_height)
                self.assertEqual((grown_card['x'], grown_card['y']), saved_position)
                self.assertTrue(overlaps(old_label, grown_card), 'fixture must exercise a real new collision')
                self.assertEqual(new_label['id'], old_label['id'])
                self.assertEqual(new_label['customData']['labelPlacement'], 'auto')
                self.assertNotEqual((new_label['x'], new_label['y']), (old_label['x'], old_label['y']))
                self.assert_auto_labels_clear_cards(refreshed)
                self.assertIn(note, refreshed['elements'])
                self.assertIn('synthetic-run-growing', by_key(refreshed, 'text', 'growing:body')['text'])
                self.assertIn('long synthetic result', by_key(refreshed, 'text', 'growing:body')['text'])
                self.assertEqual({element['customData']['target'] for element in managed(refreshed, 'node-link')},
                                 {'/tmp/synthetic-output/results', '/tmp/synthetic-output/best.pt'})
                markdown = registry_path.with_suffix('.md').read_text(encoding='utf-8')
                self.assertIn(experiments[-1]['results'][0], markdown)
                self.assertIn('synthetic-run-growing', markdown)
                self.assert_outputs_unchanged_on_repeat(registry_path)

    def test_multi_edge_growth_repairs_a_label_covered_by_another_card(self):
        layout = [
            ('model', 80, 480, 'common'),
            ('data', 80, 840, 'common'),
            ('baseline', 820, 210, 'comparison'),
            ('variant', 1560, 650, 'comparison'),
        ]
        experiments = []
        for name, position_x, position_y, group in layout:
            experiment = node(name, status='planned')
            experiment['display'] = {'x': position_x, 'y': position_y, 'group': group}
            experiments.append(experiment)
        edges = [
            {'from': 'baseline', 'to': 'model', 'relation': 'uses_model'},
            {'from': 'baseline', 'to': 'data', 'relation': 'uses_data'},
            {'from': 'variant', 'to': 'model', 'relation': 'uses_model'},
            {'from': 'variant', 'to': 'data', 'relation': 'uses_data'},
            {'from': 'baseline', 'to': 'variant', 'relation': 'compares_to'},
        ]
        data = registry(nodes=experiments, edges=edges)
        self.registry_path.write_text(json.dumps(data), encoding='utf-8')
        self.assert_cli_success(self.registry_path)
        diagram_path = self.registry_path.with_suffix('.excalidraw')
        planned = json.loads(diagram_path.read_text(encoding='utf-8'))
        key = '["variant","uses_model","model",0]'
        old_label = by_key(planned, 'edge-label', key)
        old_baseline = by_key(planned, 'node', 'baseline')
        old_variant = by_key(planned, 'node', 'variant')
        self.assertFalse(overlaps(old_label, old_baseline))
        for experiment in experiments[2:]:
            record_run_and_results(experiment)
        self.registry_path.write_text(json.dumps(data), encoding='utf-8')
        self.assert_cli_success(self.registry_path)
        refreshed = json.loads(diagram_path.read_text(encoding='utf-8'))
        grown_baseline = by_key(refreshed, 'node', 'baseline')
        grown_variant = by_key(refreshed, 'node', 'variant')
        self.assertGreater(grown_baseline['height'], old_baseline['height'])
        self.assertGreater(grown_variant['height'], old_variant['height'])
        self.assertTrue(overlaps(old_label, grown_baseline))
        relocated = by_key(refreshed, 'edge-label', key)
        self.assertEqual(relocated['id'], old_label['id'])
        self.assertNotEqual((relocated['x'], relocated['y']), (old_label['x'], old_label['y']))
        self.assertEqual(len(managed(refreshed, 'edge-label')), len(edges))
        self.assertTrue(all(label['customData'].get('labelPlacement') == 'auto'
                            for label in managed(refreshed, 'edge-label')))
        self.assert_auto_labels_clear_cards(refreshed)
        self.assert_outputs_unchanged_on_repeat(self.registry_path)

    def test_manual_and_edited_legacy_labels_remain_even_over_a_card(self):
        for mode in ('moved-auto', 'explicit-manual', 'edited-legacy'):
            with self.subTest(mode=mode):
                root = self.root / mode
                root.mkdir()
                registry_path = root / 'registry.json'
                diagram_path = registry_path.with_suffix('.excalidraw')
                registry_path.write_text(json.dumps(registry()), encoding='utf-8')
                self.assert_cli_success(registry_path)
                document = json.loads(diagram_path.read_text(encoding='utf-8'))
                label = managed(document, 'edge-label')[0]
                card = by_key(document, 'node', 'exp-a')
                original_auto = (label['customData']['autoX'], label['customData']['autoY'])
                label['x'], label['y'] = card['x'] + 30, card['y'] + 30
                label['version'] += 1
                self.assertTrue(overlaps(label, card))
                if mode == 'explicit-manual':
                    label['customData'].update(labelPlacement='manual', autoX=label['x'], autoY=label['y'])
                elif mode == 'edited-legacy':
                    for field in ('labelPlacement', 'autoX', 'autoY'):
                        label['customData'].pop(field)
                    digest = hashlib.sha256(label['id'].encode('utf-8')).hexdigest()
                    self.assertEqual(label['version'], 2)
                    self.assertEqual(label['seed'], int(digest[:8], 16) & 0x7fffffff)
                    self.assertEqual(label['versionNonce'], int(digest[8:16], 16) & 0x7fffffff)
                else:
                    self.assertNotEqual((label['x'], label['y']), original_auto)
                saved_position = (label['x'], label['y'])
                diagram_path.write_text(json.dumps(document), encoding='utf-8')
                self.assert_cli_success(registry_path)
                refreshed = json.loads(diagram_path.read_text(encoding='utf-8'))
                retained = managed(refreshed, 'edge-label')[0]
                self.assertEqual((retained['x'], retained['y']), saved_position)
                self.assertEqual(retained['customData']['labelPlacement'], 'manual')
                self.assertTrue(overlaps(retained, by_key(refreshed, 'node', 'exp-a')))
                self.assert_outputs_unchanged_on_repeat(registry_path)

    def test_auto_label_follows_changed_route_even_without_card_collision(self):
        experiments = [node('source', status='planned'), node('target', status='planned')]
        data = registry(nodes=experiments, edges=[
            {'from': 'source', 'to': 'target', 'relation': 'derived_from'},
        ])
        self.registry_path.write_text(json.dumps(data), encoding='utf-8')
        self.assert_cli_success(self.registry_path)
        diagram_path = self.registry_path.with_suffix('.excalidraw')
        planned = json.loads(diagram_path.read_text(encoding='utf-8'))
        old_label = managed(planned, 'edge-label')[0]
        old_arrow = managed(planned, 'edge')[0]
        self.assertLessEqual(label_route_distance(old_label, old_arrow), 12)
        old_heights = {card['customData']['key']: card['height'] for card in managed(planned, 'node')}
        for experiment in experiments:
            record_run_and_results(experiment)
        self.registry_path.write_text(json.dumps(data), encoding='utf-8')
        self.assert_cli_success(self.registry_path)
        refreshed = json.loads(diagram_path.read_text(encoding='utf-8'))
        cards = managed(refreshed, 'node')
        for card in cards:
            self.assertGreater(card['height'], old_heights[card['customData']['key']])
            self.assertFalse(overlaps(old_label, card))
        new_arrow = managed(refreshed, 'edge')[0]
        new_label = managed(refreshed, 'edge-label')[0]
        self.assertGreater(label_route_distance(old_label, new_arrow), 100)
        self.assertEqual(new_label['id'], old_label['id'])
        self.assertEqual(new_label['customData']['labelPlacement'], 'auto')
        self.assertLessEqual(label_route_distance(new_label, new_arrow), 12)
        self.assert_auto_labels_clear_cards(refreshed)
        self.assert_outputs_unchanged_on_repeat(self.registry_path)

    def test_earlier_auto_label_avoids_later_manual_label(self):
        data = registry(edges=[
            {'from': 'exp-a', 'to': 'exp-b', 'relation': 'derived_from'},
            {'from': 'exp-a', 'to': 'exp-b', 'relation': 'compares_to'},
        ])
        self.registry_path.write_text(json.dumps(data), encoding='utf-8')
        self.assert_cli_success(self.registry_path)
        diagram_path = self.registry_path.with_suffix('.excalidraw')
        document = json.loads(diagram_path.read_text(encoding='utf-8'))
        automatic, manual = managed(document, 'edge-label')
        manual['x'], manual['y'] = automatic['x'], automatic['y']
        manual['customData']['labelPlacement'] = 'manual'
        manual['version'] += 1
        saved_position = (manual['x'], manual['y'])
        self.assertTrue(overlaps(automatic, manual))
        diagram_path.write_text(json.dumps(document), encoding='utf-8')
        self.assert_cli_success(self.registry_path)
        refreshed = json.loads(diagram_path.read_text(encoding='utf-8'))
        new_auto = by_key(refreshed, 'edge-label', automatic['customData']['key'])
        new_manual = by_key(refreshed, 'edge-label', manual['customData']['key'])
        self.assertEqual((new_manual['x'], new_manual['y']), saved_position)
        self.assertEqual(new_manual['customData']['labelPlacement'], 'manual')
        self.assertEqual(new_auto['customData']['labelPlacement'], 'auto')
        self.assertFalse(overlaps(new_auto, new_manual))
        self.assert_auto_labels_clear_cards(refreshed)
        self.assert_outputs_unchanged_on_repeat(self.registry_path)

    def test_default_both_stable_ids_noop_and_bindings(self):
        result = call(self.registry_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        markdown = self.registry_path.with_suffix('.md')
        diagram_path = self.registry_path.with_suffix('.excalidraw')
        self.assertTrue(markdown.exists())
        self.assertTrue(diagram_path.exists())
        document = json.loads(diagram_path.read_text(encoding='utf-8'))
        ids = [element['id'] for element in document['elements']]
        self.assertEqual(len(ids), len(set(ids)))
        texts = [element for element in document['elements'] if element['type'] == 'text']
        self.assertTrue(texts)
        self.assertEqual({element.get('fontFamily') for element in texts}, {5})
        self.assertIn('legacy, main', by_key(document, 'text', 'exp-b:body')['text'])
        shape_ids = {element['id'] for element in managed(document, 'node')}
        for arrow in managed(document, 'edge'):
            self.assertIn(arrow['startBinding']['elementId'], shape_ids)
            self.assertIn(arrow['endBinding']['elementId'], shape_ids)
            for endpoint in ('startBinding', 'endBinding'):
                shape = next(e for e in managed(document, 'node') if e['id'] == arrow[endpoint]['elementId'])
                self.assertIn({'id': arrow['id'], 'type': 'arrow'}, shape['boundElements'])
        ids_before = set(ids)
        times_before = (markdown.stat().st_mtime_ns, diagram_path.stat().st_mtime_ns)
        time.sleep(0.02)
        result = call(self.registry_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        document_after = json.loads(diagram_path.read_text(encoding='utf-8'))
        self.assertEqual(ids_before, {element['id'] for element in document_after['elements']})
        self.assertEqual(times_before, (markdown.stat().st_mtime_ns, diagram_path.stat().st_mtime_ns))

    def test_incremental_refresh_keeps_layout_style_notes_files_and_app_state(self):
        self.assertEqual(call(self.registry_path).returncode, 0)
        diagram_path = self.registry_path.with_suffix('.excalidraw')
        original = json.loads(diagram_path.read_text(encoding='utf-8'))
        saved_node = by_key(original, 'node', 'exp-a')
        saved_node['x'], saved_node['y'] = 1450, 380
        saved_node['backgroundColor'] = '#123456'
        saved_label = by_key(original, 'edge-label', '["exp-a","derived_from","exp-b",0]')
        saved_label['x'], saved_label['y'] = 1050, 520
        manual = {'id': 'manual-note', 'type': 'rectangle', 'x': 80, 'y': 190, 'width': 460, 'height': 180,
                  'angle': 0, 'strokeColor': '#7048e8', 'backgroundColor': '#f3f0ff', 'fillStyle': 'solid',
                  'strokeWidth': 2, 'strokeStyle': 'solid', 'roughness': 0, 'opacity': 100, 'groupIds': [],
                  'frameId': None, 'index': 'a999', 'roundness': {'type': 3}, 'seed': 991, 'version': 1,
                  'versionNonce': 991, 'isDeleted': False, 'boundElements': None, 'updated': 1,
                  'link': None, 'locked': False, 'customData': {'author': 'human'}}
        original['elements'].append(manual)
        negative_arrow = {'id': 'manual-negative-arrow', 'type': 'arrow', 'x': 560, 'y': 750, 'width': 560, 'height': 500,
                          'angle': 0, 'strokeColor': '#7048e8', 'backgroundColor': 'transparent', 'fillStyle': 'solid',
                          'strokeWidth': 2, 'strokeStyle': 'solid', 'roughness': 0, 'opacity': 100, 'groupIds': [],
                          'frameId': None, 'points': [[0, 0], [-560, -500]], 'roundness': {'type': 2},
                          'startBinding': None, 'endBinding': None, 'startArrowhead': None, 'endArrowhead': 'arrow',
                          'lastCommittedPoint': None, 'index': 'a1000', 'seed': 992, 'version': 1,
                          'versionNonce': 992, 'isDeleted': False, 'boundElements': None, 'updated': 1,
                          'link': None, 'locked': False}
        original['elements'].append(negative_arrow)
        original['appState']['theme'] = 'light'
        original['files'] = {'kept-file': {'mimeType': 'image/png', 'dataURL': 'data:image/png;base64,AA=='}}
        diagram_path.write_text(json.dumps(original, ensure_ascii=False), encoding='utf-8')
        old_geometry = [e for e in original['elements'] if not e.get('isDeleted')]

        updated_data = registry(
            nodes=[
                node('exp-a', status='finished', title='updated baseline title', changes=['facts refreshed']),
                node('exp-b', status='failed', changes=['failure state imported']),
                node('exp-c', status='unknown', title='new historical import', changes=['long synthetic detail ' * 14], revisions=[
                    {'id': 'old', 'repo': 'fictional-repo', 'branch': 'branch/older', 'commit': '333333',
                     'worktree': None, 'host': None, 'observed_at': '2024-05-01', 'code_snapshot': None,
                     'patch_path': None, 'dirty': False},
                    {'id': 'new', 'repo': 'fictional-repo', 'branch': 'branch/current', 'commit': '444444',
                     'worktree': None, 'host': None, 'observed_at': '2026-11-03', 'code_snapshot': None,
                     'patch_path': None, 'dirty': False},
                ]),
            ],
            edges=[{'from': 'exp-a', 'to': 'exp-b', 'relation': 'compares_to'},
                   {'from': 'exp-c', 'to': 'exp-a', 'relation': 'continues_from'}],
        )
        self.registry_path.write_text(json.dumps(updated_data, ensure_ascii=False), encoding='utf-8')
        result = call(self.registry_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(diagram_path.read_text(encoding='utf-8'))
        self.assertEqual(output['appState'], original['appState'])
        self.assertEqual(output['files'], original['files'])
        self.assertIn(manual, output['elements'])
        self.assertEqual((by_key(output, 'node', 'exp-a')['x'], by_key(output, 'node', 'exp-a')['y']), (1450, 380))
        self.assertEqual(by_key(output, 'node', 'exp-a')['backgroundColor'], '#123456')
        self.assertEqual(by_key(output, 'node', 'exp-b')['backgroundColor'], '#fff0f0')
        self.assertEqual((by_key(output, 'edge-label', '["exp-a","compares_to","exp-b",0]')['x'],
                          by_key(output, 'edge-label', '["exp-a","compares_to","exp-b",0]')['y']), (1050, 520))
        self.assertIn('branch/older, branch/current', by_key(output, 'text', 'exp-c:body')['text'])
        self.assertIn('updated baseline title', by_key(output, 'text', 'exp-a:body')['text'])
        self.assertFalse(any('derived_from' in e.get('customData', {}).get('key', '') for e in managed(output, 'edge')))
        compare_arrow = by_key(output, 'edge', '["exp-a","compares_to","exp-b",0]')
        self.assertEqual(compare_arrow['strokeStyle'], 'dashed')
        self.assertGreaterEqual(compare_arrow['width'], 0)
        self.assertGreaterEqual(compare_arrow['height'], 0)
        self.assertLessEqual(compare_arrow['points'][1][0], 0)
        created = by_key(output, 'node', 'exp-c')
        created_box = (created['x'] - 18, created['y'] - 18, created['x'] + created['width'] + 18, created['y'] + created['height'] + 18)
        self.assertGreaterEqual(created['width'], 0)
        self.assertGreaterEqual(created['height'], 0)
        for previous in old_geometry:
            self.assertFalse(renderer._overlaps(created_box, renderer._element_box(previous)), f"new node overlaps saved {previous['id']}")
        for element in output['elements']:
            if element.get('customData', {}).get('managedBy') == MANAGED and element['type'] == 'text':
                self.assertEqual(element['fontFamily'], 5)
                self.assertLessEqual(max((renderer._text_width(line, element['fontSize']) for line in element['text'].splitlines()), default=0), element['width'] * 0.88 + 1)
                self.assertLessEqual(renderer._line_count(element['text']) * element['fontSize'] * element['lineHeight'], element['height'] + 1)
                parent = next(e for e in output['elements'] if e['id'] == element['containerId'])
                self.assertIn({'id': element['id'], 'type': 'text'}, parent['boundElements'])
                self.assertEqual(sum(binding.get('type') == 'text' for binding in parent['boundElements']), 1)

    def test_single_formats_and_permissions(self):
        markdown = self.root / 'custom.md'
        diagram = self.root / 'custom.excalidraw'
        result = call(self.registry_path, '--format', 'markdown', '--output', markdown)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(markdown.exists())
        self.assertFalse(diagram.exists())
        result = call(self.registry_path, '--format', 'excalidraw', '--excalidraw-output', diagram)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(diagram.exists())
        self.assertFalse((self.root / 'registry.md').exists())
        markdown.chmod(0o640)
        diagram.chmod(0o600)
        self.registry_path.write_text(json.dumps(registry(nodes=[node('exp-a', title='permission update')], edges=[]), ensure_ascii=False), encoding='utf-8')
        result = call(self.registry_path, '--format', 'both', '--output', markdown, '--excalidraw-output', diagram)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stat.S_IMODE(markdown.stat().st_mode), 0o640)
        self.assertEqual(stat.S_IMODE(diagram.stat().st_mode), 0o600)
        fresh = self.root / 'fresh.md'
        old_umask = os.umask(0)
        os.umask(old_umask)
        result = call(self.registry_path, '--format', 'markdown', '--output', fresh)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stat.S_IMODE(fresh.stat().st_mode), 0o666 & ~old_umask)

    def test_parallel_relations_have_separate_lanes_and_deleted_shapes_restore(self):
        self.registry_path.write_text(json.dumps(registry(edges=[
            {'from': 'exp-a', 'to': 'exp-b', 'relation': 'derived_from'},
            {'from': 'exp-a', 'to': 'exp-b', 'relation': 'compares_to'},
        ]), ensure_ascii=False), encoding='utf-8')
        result = call(self.registry_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        diagram_path = self.registry_path.with_suffix('.excalidraw')
        document = json.loads(diagram_path.read_text(encoding='utf-8'))
        arrows = managed(document, 'edge')
        labels = managed(document, 'edge-label')
        self.assertEqual(len(arrows), 2)
        self.assertNotEqual(arrows[0]['y'], arrows[1]['y'])
        self.assertFalse(overlaps(labels[0], labels[1]))
        node_shape = by_key(document, 'node', 'exp-a')
        node_shape['isDeleted'] = True
        node_text = by_key(document, 'text', 'exp-a:body')
        node_text['isDeleted'] = True
        arrows[0]['isDeleted'] = True
        diagram_path.write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
        result = call(self.registry_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        restored = json.loads(diagram_path.read_text(encoding='utf-8'))
        self.assertFalse(by_key(restored, 'node', 'exp-a')['isDeleted'])
        self.assertFalse(by_key(restored, 'text', 'exp-a:body')['isDeleted'])
        self.assertTrue(all(not e['isDeleted'] for e in managed(restored, 'edge')))

    def test_invalid_existing_diagram_preserves_both_outputs(self):
        markdown = self.root / 'keep.md'
        diagram = self.root / 'broken.excalidraw'
        markdown.write_text('markdown sentinel', encoding='utf-8')
        diagram.write_text('{ invalid json', encoding='utf-8')
        result = call(self.registry_path, '--format', 'both', '--output', markdown, '--excalidraw-output', diagram)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Invalid existing Excalidraw JSON', result.stderr)
        self.assertEqual(markdown.read_text(encoding='utf-8'), 'markdown sentinel')
        self.assertEqual(diagram.read_text(encoding='utf-8'), '{ invalid json')

    def test_colliding_paths_are_rejected_before_writes(self):
        old = self.registry_path.read_text(encoding='utf-8')
        result = call(self.registry_path, '--format', 'both', '--output', self.registry_path,
                      '--excalidraw-output', self.registry_path)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.registry_path.read_text(encoding='utf-8'), old)


if __name__ == '__main__':
    unittest.main(verbosity=2)
