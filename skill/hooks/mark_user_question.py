#!/usr/bin/env python3
"""
PostToolUse hook (matcher: "AskUserQuestion") — records (a) that the agent asked the user a
question (`question`: all question strings and option labels joined) and (b) what the user
ANSWERED (`answer`: raw response text + [question, answer] pairs parsed from `tool_response`).
The AIDD rules use these as evidence that a human was actually consulted and said yes (e.g.
before tasks.md approval). Always exits 0; a recorder failure never breaks the session.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event  # noqa: E402

event = read_event()
if not isinstance(event, dict):
    event = {}
_sid = event.get('session_id') if isinstance(event.get('session_id'), str) else None
_cwd = event.get('cwd') if isinstance(event.get('cwd'), str) and event.get('cwd') else None

try:
    sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
    import aidd_evidence as _ev
    _root = _ev.find_root(_cwd or Path.cwd())
    _ti = event.get('tool_input')
    _qs = _ti.get('questions') if isinstance(_ti, dict) else None
    _parts = []
    _known = []      # question strings, in order — the ONLY anchors used to parse the answers
    _options = []    # option labels offered per question, aligned with _known
    _clean = True
    for _q in (_qs if isinstance(_qs, list) else []):
        if not isinstance(_q, dict) or not isinstance(_q.get('question'), str):
            _clean = False
            continue
        _parts.append(_q['question'])
        _known.append(_q['question'])
        _labels = []
        _opts = _q.get('options')
        for _o in (_opts if isinstance(_opts, list) else []):
            if isinstance(_o, dict):
                if isinstance(_o.get('label'), str):
                    _labels.append(_o['label'])
            elif isinstance(_o, str):
                _labels.append(_o)
        _options.append(_labels)
        _parts.extend(_labels)
    _ev.append_question(_root, _sid, ' | '.join(p for p in _parts if p), options=_options)
    _resp = event.get('tool_response')
    if _resp is not None:
        _text, _pairs = _ev.parse_answers(_resp, _known if _clean else [])
        _ev.append_answer(_root, _sid, _text, _pairs, options=_options if _pairs else None)
except Exception as _e:
    try:
        _ev.record_hook_error(_cwd, _sid, 'mark_user_question', _e)
    except Exception:
        pass

sys.exit(0)
