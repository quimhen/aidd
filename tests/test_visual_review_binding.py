"""Visual-review evidence must track the audited local design snapshot."""
import hashlib
import sys
from types import SimpleNamespace
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'hooks'))
import aidd_review as review
import aidd_rules
import aidd_status
import rule_gate


def make_spec(tmp_path):
    (tmp_path / '.aidd').mkdir()
    spec = tmp_path / 'specs' / 'visual'
    spec.mkdir(parents=True)
    (spec / 'spec.md').write_text('# Spec\n\n## Requirements\n| Code | Requirement |\n|---|---|\n| FR-001 | Show form |\n', encoding='utf-8')
    (spec / 'tasks.md').write_text('# Tasks\n\n| Task | Target file |\n|---|---|\n| T-01 | form.tsx |\n', encoding='utf-8')
    snap = tmp_path / 'mockup.png'
    snap.write_bytes(b'design version one')
    return spec, snap


def audit(spec, snap, sha=None):
    sha = sha or hashlib.sha256(snap.read_bytes()).hexdigest()
    (spec / 'mockup-audit.md').write_text(
        '# Audit\n\n## Provenance\n| Field | Value |\n|---|---|\n'
        f'| Visual snapshot | mockup.png |\n| Visual snapshot SHA-256 | {sha} |\n'
        '\n## Screen inventory\n| SCREEN-XX | Name |\n|---|---|\n| SCREEN-01 | Form |\n', encoding='utf-8')


def test_changed_missing_or_unrecorded_snapshot_never_passes(tmp_path):
    spec, snap = make_spec(tmp_path)
    audit(spec, snap)
    before = review.sources_digest(spec)
    assert review.sources_digest(spec) == before
    snap.write_bytes(b'design version two')
    with pytest.raises(ValueError, match='changed since its audit'):
        review.sources_digest(spec)
    assert not review.review_state(spec)['complete']
    audit(spec, snap)
    assert review.sources_digest(spec) != before
    snap.unlink()
    with pytest.raises(ValueError, match='missing'):
        review.sources_digest(spec)


def test_new_snapshot_changes_all_item_digests(tmp_path):
    spec, snap = make_spec(tmp_path)
    audit(spec, snap)
    first = review.build_html(spec)
    page = spec / 'review.html'
    page.write_text(first, encoding='utf-8')
    old = review._page_digests(page)
    assert old
    snap.write_bytes(b'design version two')
    audit(spec, snap)
    page.write_text(review.build_html(spec), encoding='utf-8')
    new = review._page_digests(page)
    assert set(old) == set(new)
    assert all(old[code] != new[code] for code in old)


def test_incomplete_external_and_escape_declarations_are_refused(tmp_path):
    spec, snap = make_spec(tmp_path)
    for name, sha in [('https://figma.com/design', 'a' * 64), ('../../outside', 'a' * 64), ('mockup.png', ''), ('', '')]:
        (spec / 'mockup-audit.md').write_text(
            f'## Provenance\n| Field | Value |\n|---|---|\n| Visual snapshot | {name} |\n'
            f'| Visual snapshot SHA-256 | {sha} |\n', encoding='utf-8')
        with pytest.raises(ValueError):
            review.sources_digest(spec)


def test_legacy_review_digest_is_unchanged(tmp_path):
    spec, _ = make_spec(tmp_path)
    (spec / 'mockup-audit.md').write_text('## Provenance\n| Source | legacy |\n', encoding='utf-8')
    assert review.sources_digest(spec) == review._digest_of(review._load_sources(spec))


def test_snapshot_resolution_error_fails_closed(tmp_path):
    spec, snap = make_spec(tmp_path)
    audit(spec, snap)
    with mock.patch.object(review, '_visual_binding_unchecked', side_effect=OSError('unreadable')):
        state = review.review_state(spec)
    assert not state['complete']
    assert 'visual snapshot cannot be verified' in state['visual_source_error']


def test_approval_binding_blocks_code_and_close_after_new_snapshot(tmp_path):
    spec, snap = make_spec(tmp_path)
    audit(spec, snap)
    old = review._visual_binding(spec, (spec / 'mockup-audit.md').read_text(encoding='utf-8'))
    snap.write_bytes(b'design version two')
    audit(spec, snap)
    evidence = SimpleNamespace(latest_approved=lambda *_: {'visual_snapshot': old})
    with mock.patch.object(rule_gate, '_approved_recorded', return_value=True), \
         mock.patch.object(rule_gate, '_review_lib', return_value=review), \
         mock.patch.object(aidd_rules, 'approval_valid', return_value=True):
        violation = rule_gate._target_violation(evidence, aidd_rules, tmp_path, spec.name, 'test')
    assert 'visual snapshot changed after approval' in violation['message']
    with mock.patch.object(aidd_status, '_approval_recorded', return_value=True), \
         mock.patch.object(aidd_status, '_review_mod', return_value=review), \
         mock.patch.object(aidd_status.ev, 'latest_approved', return_value={'visual_snapshot': old}), \
         mock.patch.object(aidd_rules, 'approval_valid', return_value=True), \
         mock.patch.object(aidd_status, '_gate_version', return_value=0):
        gaps = aidd_status._close_gaps(spec, tmp_path)
    assert any('visual snapshot changed after approval' in gap for gap in gaps)
