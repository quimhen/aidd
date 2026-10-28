"""Tests for the script's evidence and fail-closed status; no database needed."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / 'skill' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import aidd_readiness as readiness


@pytest.fixture
def spec(tmp_path):
    d = tmp_path / 'specs' / 'example'
    d.mkdir(parents=True)
    (d / 'spec.md').write_text('| FR-001 | US-002 |\n', encoding='utf-8')
    (d / 'plan.md').write_text('| FR-001 | T-003 |\n', encoding='utf-8')
    (d / 'tasks.md').write_text('| T-003 | SCREEN-01 |\n', encoding='utf-8')
    return d


def done(code=0):
    return subprocess.CompletedProcess([], code, 'mechanical output', '')


def test_reports_explicit_line_references_and_real_hashes(spec, monkeypatch):
    calls = []
    monkeypatch.setattr(readiness.subprocess, 'run', lambda *a, **kw: calls.append(a) or done())
    result = readiness.report(spec)
    assert result['status'] == 'checked'
    assert len(calls) == 1
    assert len(result['observed_input_sha256']['spec.md']) == 64
    assert {'file': 'plan.md', 'line': 1, 'codes': ['FR-001', 'T-003']} in result['references_by_line']
    assert 'no approval' in result['notice']
    assert result['checker']['stdout'] == 'mechanical output'


def test_missing_required_artifact_is_not_checked(spec, monkeypatch):
    (spec / 'plan.md').unlink()
    monkeypatch.setattr(readiness.subprocess, 'run', lambda *a, **kw: done())
    result = readiness.report(spec)
    assert result['status'] == 'incomplete'
    assert result['missing_required_artifacts'] == ['plan.md']


def test_changed_input_during_checker_is_unstable(spec, monkeypatch):
    def changed(*args, **kwargs):
        (spec / 'tasks.md').write_text('updated T-003', encoding='utf-8')
        return done()
    monkeypatch.setattr(readiness.subprocess, 'run', changed)
    result = readiness.report(spec)
    assert result['status'] == 'unstable'
    assert result['changed_observed_inputs'] == ['tasks.md']


@pytest.mark.parametrize('code,status', [(1, 'gaps'), (2, 'checker_error')])
def test_checker_failures_are_preserved(spec, monkeypatch, code, status):
    monkeypatch.setattr(readiness.subprocess, 'run', lambda *a, **kw: done(code))
    result = readiness.report(spec)
    assert result['status'] == status
    assert result['checker']['exit_code'] == code


def test_pending_approval_and_implementation_refs_are_deferred(spec, monkeypatch):
    (spec / 'tasks.md').write_text('Approved: PENDING\n| T-003 | SCREEN-01 |\n', encoding='utf-8')
    output = ('1. R6 tasks.md has no valid "Approved: YYYY-MM-DD hash:<12hex>" line (approval pending).\n'
              '2. plan.md: 2 row(s) with an empty PR/Spec ref — fine before implementation, a gap once Step 5 has started.\n')
    monkeypatch.setattr(readiness.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess([], 1, output, ''))
    result = readiness.report(spec)
    assert result['status'] == 'checked'
    assert len(result['checker']['deferred_until_approval_or_implementation']) == 2
    assert result['checker']['exit_code'] == 1


def test_invalid_approval_is_not_deferred(spec, monkeypatch):
    (spec / 'tasks.md').write_text('Approved: invalid\n', encoding='utf-8')
    output = '1. R6 tasks.md has no valid "Approved: YYYY-MM-DD hash:<12hex>" line (approval pending).\n'
    monkeypatch.setattr(readiness.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess([], 1, output, ''))
    assert readiness.report(spec)['status'] == 'gaps'


def test_cli_does_not_overwrite_existing_output(spec, tmp_path, monkeypatch):
    monkeypatch.setattr(readiness.subprocess, 'run', lambda *a, **kw: done())
    target = spec / 'tasks.md'
    original = target.read_text(encoding='utf-8')
    assert readiness.main([str(spec), '--output', str(target)]) == 2
    assert target.read_text(encoding='utf-8') == original


def test_real_checker_is_invoked(spec):
    result = readiness.report(spec)
    assert result['checker']['exit_code'] == 1
    assert result['status'] == 'gaps'
    assert 'STRUCTURAL CHECK ONLY' in result['checker']['stdout']
