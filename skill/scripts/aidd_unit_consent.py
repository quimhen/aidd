"""Canonicalize a complete unit-review question without fabricating consent."""
from __future__ import annotations

import hashlib
import json


def unit_question_semantic_sha256(question: str) -> str:
    """Bind all reviewed fields while excluding administrative task status.

    This identifies the question; it does not prove it was shown or answered.
    Only a trusted hook may attach it to an anchored owner response.
    """
    try:
        from . import aidd_rules as rules
    except ImportError:
        import aidd_rules as rules
    if not isinstance(question, str) or '\n' not in question:
        raise ValueError('invalid unit question')
    _, package = question.split('\n', 1)
    try:
        data = json.loads(package)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid unit review JSON') from exc
    base = {'format', 'unit', 'project', 'digest', 'parents', 'targets', 'tasks'}
    v2 = base | {'version', 'inputs', 'config', 'visual_refs'}
    if (not isinstance(data, dict) or set(data) not in (base, v2)
            or (data.get('format') == 'aidd-unit-review-v1' and set(data) != base)
            or (data.get('format') == 'aidd-unit-review-v2' and set(data) != v2)):
        raise ValueError('invalid unit review fields')
    if json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(',', ':')) != package:
        raise ValueError('unit review package is not canonical')
    if rules.unit_consent_question(package) != question:
        raise ValueError('question does not match unit review package')
    if any(not isinstance(data[key], list) or any(not isinstance(x, str) for x in data[key])
           for key in ('parents', 'targets')):
        raise ValueError('invalid unit review dependencies')
    if not isinstance(data['tasks'], list) or not data['tasks']:
        raise ValueError('unit review has no tasks')
    tasks, paths = [], set()
    for item in data['tasks']:
        if (not isinstance(item, dict) or set(item) != {'path', 'content'}
                or not isinstance(item['path'], str) or not item['path']
                or not isinstance(item['content'], str) or item['path'] in paths):
            raise ValueError('invalid unit task review')
        paths.add(item['path'])
        projection = rules.approval_projection(item['content'])
        if projection is None or not projection.strip():
            raise ValueError('unit task review cannot be projected')
        tasks.append({'path': item['path'], 'content': projection})
    normalized = {**data, 'tasks': tasks, 'semantic_format': 'aidd-unit-question-v1'}
    encoded = json.dumps(normalized, sort_keys=True, ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()
