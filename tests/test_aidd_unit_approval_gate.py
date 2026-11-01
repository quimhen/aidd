import json

from skill.scripts import aidd_rules as rules


class Evidence:
    def __init__(self):
        self.rows = []

    def events(self, root, kind=None):
        return self.rows


def test_only_semantically_changed_unit_loses_approval(tmp_path):
    spec = '001-example'
    paths = []
    for sequence, name in enumerate(('first', 'second'), 1):
        directory = tmp_path / 'specs' / spec / 'amendments' / name
        directory.mkdir(parents=True)
        task = directory / 'tasks.md'
        task.write_text('| Task | Status | Tracker ref |\n| --- | --- | --- |\n| Build feature | Pending | 1 |\n', encoding='utf-8')
        relative = task.relative_to(tmp_path).as_posix()
        manifest = {'schema_version': 2, 'spec_id': spec, 'unit_id': name, 'sequence': sequence,
                    'parents': [], 'paths': [relative], 'targets': [f'src/{name}.py'],
                    'version': 'v1', 'inputs': [], 'config': [], 'visual_refs': []}
        (directory / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        paths.append(task)
    evidence = Evidence()
    states = rules.unit_approval_states(tmp_path, spec, evidence)
    assert not any(s['approved'] for s in states)
    for state in states:
        evidence.rows.append({'detail': {'spec': spec, 'unit_id': state['unit'],
                                         'digest': state['digest'], 'review_sha256': 'a' * 64}})
    paths[0].write_text(paths[0].read_text(encoding='utf-8').replace('Pending | 1', 'Done | 2'), encoding='utf-8')
    assert all(s['approved'] for s in rules.unit_approval_states(tmp_path, spec, evidence))
    paths[0].write_text(paths[0].read_text(encoding='utf-8').replace('Build feature', 'Build changed feature'), encoding='utf-8')
    states = {s['unit']: s['approved'] for s in rules.unit_approval_states(tmp_path, spec, evidence)}
    assert states == {'first': False, 'second': True}
