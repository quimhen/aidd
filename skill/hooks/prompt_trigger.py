#!/usr/bin/env python3
"""
UserPromptSubmit hook — scans the user's own message for requirement/change
keywords and, on a match, injects an instruction telling Claude to invoke the
aidd skill before doing anything else. It also does the Step -1 legwork
itself: it runs find_spec.py against the prompt's own keywords and includes
the result inline, so Claude opens the skill already holding the search
verdict (match / no match, and which spec) instead of needing a separate
tool round-trip to get it. The point is zero extra action from the user —
one ordinary prompt about a change is enough to get the full pipeline moving.

This is the EARLY gate: it fires at the planning stage, before any file exists,
so aidd gets engaged from the first message about a requirement/feature —
not only once code-writing is already underway (that's require_aidd.py's job,
as a hard fallback for sessions that reach Write/Edit some other way, e.g. if
this hook's advisory gets missed).

Edit TRIGGER_KEYWORDS below to tune what counts as "this needs aidd" — keep
it to genuine requirement/change/new-feature language, not every message.

Language coverage — this hook is one advisory layer among several, not the
only thing standing between a non-English/non-Spanish prompt and AIDD:
  - TRIGGER_KEYWORDS covers English, Spanish, Portuguese, and a handful of
    literal CJK terms. It does NOT cover every language — a prompt in, say,
    French or Arabic simply won't fire this specific early nudge.
  - Even when this hook stays silent, AIDD still engages for two other
    reasons: (1) the skill's own frontmatter `description` is matched by the
    model semantically, not by this regex, so Claude can decide to invoke
    aidd for a request in any language on its own judgment; (2)
    require_aidd.py is a hard, language-agnostic gate on Write/Edit that
    doesn't read the prompt at all — it blocks regardless of what language
    the request was made in.
  - CJK tokenization here (see query_terms_from_prompt) is substring-level,
    not word-segmented (CJK has no spaces to split on, and a real segmenter
    is a dependency this stdlib-only hook intentionally doesn't carry) — it
    still works for search/matching, just at coarser granularity than
    Latin-script languages.
"""
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event  # noqa: E402

TRIGGER_KEYWORDS = [
    r'requerimientos?',
    r'levantamiento',
    r'planificar',
    r'planificaci[oó]n',
    r'\bplan\b',
    r'nuevo proyecto',
    r'nueva funcionalidad',
    r'funcionalidad(es)?',
    # Any change verb, not only "plan/planificar" — mejorar/crear/desarrollar/
    # actualizar/modificar are exactly the verbs the user asked this to cover.
    r'mejorar',
    r'\bcrear\b',
    r'desarrollar',
    r'actualizar',
    r'modificar',
    r'agregar',
    r'a[ñn]adir',
    # Non-UI triggers — AIDD is the default pipeline for ANY change, not only UI work.
    r'implementar',
    r'arregl(ar|a)',
    r'corregi[rn]',
    r'\bbug\b',
    r'\bfix\b',
    r'endpoint',
    r'api\b',
    r'stored procedure',
    r'migraci[oó]n',
    r'refactor',
    r'backend',
    # Portuguese — same change-verb coverage as the Spanish list above.
    r'melhorar',
    r'\bcriar\b',
    r'desenvolver',
    r'atualizar',
    r'corrigi[rd]',
    # A few CJK trigger terms (literal substrings — CJK has no word-boundary
    # spaces, so \b-based patterns above don't apply; a plain substring search
    # is the right tool here). Not exhaustive — see the module docstring for
    # why full CJK coverage needs a real segmenter this hook intentionally
    # doesn't carry.
    r'修改', r'创建', r'开发', r'更新', r'实现', r'优化', r'修复', r'错误', r'新功能',
]

PATTERN = re.compile('|'.join(TRIGGER_KEYWORDS), re.IGNORECASE)

STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'of', 'to', 'in', 'on', 'for', 'with',
    'this', 'that', 'is', 'it', 'de', 'la', 'el', 'los', 'las', 'un', 'una',
    'que', 'con', 'para', 'del', 'en', 'y', 'o', 'se', 'al', 'es', 'lo',
    'quiero', 'necesito', 'puedes', 'favor', 'por', 'debe', 'debes',
}


def find_specs_root(start: Path):
    cur = start.resolve()
    for _ in range(6):
        candidate = cur / 'specs'
        if candidate.is_dir():
            return candidate
        cur = cur.parent
    return None


def query_terms_from_prompt(prompt: str, limit=8):
    """Unicode-aware split (\\w+) — not a hardcoded Latin-accent whitelist —
    so Portuguese/etc. words keep their accents and a CJK phrase still yields
    a usable term instead of being silently stripped to nothing."""
    words = []
    for raw in re.findall(r'\w+', prompt, re.UNICODE):
        w = raw.strip()
        if len(w) >= 4 and w.lower() not in STOPWORDS:
            words.append(w)
        if len(words) >= limit:
            break
    return words


def run_find_spec(cwd: Path, terms):
    """Best-effort: run find_spec.py so Claude gets the Step -1 verdict inline.
    Never raises — a failure here just means the reminder ships without it,
    which is strictly no worse than before this existed."""
    if not terms:
        return None
    script = Path(__file__).parent.parent / 'scripts' / 'find_spec.py'
    if not script.exists():
        return None
    try:
        result = subprocess.run(
            [sys.executable, str(script), *terms],
            cwd=str(cwd), capture_output=True, text=True, timeout=10,
            encoding='utf-8', errors='replace',
        )
        return result.stdout.strip()
    except Exception:
        return None


event = read_event()
if not isinstance(event, dict):
    event = {}
prompt = event.get('prompt') if isinstance(event.get('prompt'), str) else ''
_sid = event.get('session_id') if isinstance(event.get('session_id'), str) else None
_cwd = event.get('cwd') if isinstance(event.get('cwd'), str) and event.get('cwd') else None

_secret_labels = []
try:  # evidence recorder — additive, must never affect output or exit code
    sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
    import aidd_evidence as _ev
    _stored, _secret_labels = _ev.redact_secrets(prompt)
    _ev.append(_ev.find_root(_cwd or Path.cwd()), _sid, 'prompt', text=_stored)
except Exception as _e:
    try:
        _ev.record_hook_error(_cwd, _sid, 'prompt_trigger', _e)
    except Exception:
        pass

if _secret_labels:  # credential hygiene warning — independent of the planning-keyword match
    try:
        print("[aidd] Credential hygiene: this message contains a secret (" + ', '.join(_secret_labels)
              + "). It was redacted from the evidence log. NEVER copy it into files, specs, memory, "
              "commands or logs; use an environment variable or a connection profile outside the chat. "
              "Next action: reference the secret by variable name only (e.g. $env:DB_PASSWORD).")
    except Exception:
        pass

if PATTERN.search(prompt):
    try:
        cwd = Path(_cwd or Path.cwd())
        specs_root = find_specs_root(cwd)
    except Exception:
        specs_root = None
    find_spec_output = None
    if specs_root is not None:
        terms = query_terms_from_prompt(prompt)
        find_spec_output = run_find_spec(specs_root.parent, terms)
        try:  # this hook itself ran find_spec: record it as evidence (source=hook)
            if find_spec_output is not None:
                import aidd_evidence as _ev
                _ev.append_find_spec(_ev.find_root(specs_root.parent), _sid,
                                     rebuilt=_ev.find_spec_rebuilt(find_spec_output),
                                     ok=_ev.find_spec_ok(find_spec_output), source='hook')
        except Exception as _e:
            try:
                _ev.record_hook_error(_cwd, _sid, 'prompt_trigger', _e)
            except Exception:
                pass

    message = [
        "[aidd] This message looks like a requirement, change, improvement, or fix. AIDD "
        "applies to ANY change (UI or not, small or large) — before responding, invoke "
        "the aidd skill (Skill tool, skill: \"aidd\") and follow its pipeline (Step -1 "
        "intake/search for an existing spec -> Step 0 visual source ONLY if there's a "
        "mockup, otherwise skip straight to Step 2 Align -> Plan -> Tasks -> Build -> "
        "Converge) instead of improvising the analysis or the plan directly in the "
        "conversation. Don't ask the user to run anything manually — the whole pipeline "
        "runs inside this same response.",
    ]
    if find_spec_output:
        message.append(
            "\n[aidd] Step -1 already ran automatically against this message "
            "(find_spec.py) — use this result as the intake's starting point, "
            "don't re-run it with the same terms:\n" + find_spec_output
        )
    print('\n'.join(message))

sys.exit(0)
