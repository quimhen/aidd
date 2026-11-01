"""Plan same-invocation observations without executing or granting PASS.

The planner is deliberately disconnected from the production verifier. A caller
must supply a real capability verifier before any plan could authorize sharing;
test doubles only exercise grouping and do not supply that capability.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Mapping, Sequence

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_REQUIRED = ("root", "cwd", "cmd", "expected", "inputs", "input_fp",
             "closure_fp", "runner_policy", "effective_timeout", "execution_context_id")


def _identity(row: Mapping[str, object]) -> tuple[str, str]:
    spec, number = row.get("spec_id"), row.get("row_id")
    if not isinstance(spec, str) or not spec or not isinstance(number, str) or not number:
        raise ValueError("participant needs nonempty spec_id and row_id")
    return spec, number


def _candidate(row: Mapping[str, object]) -> tuple[tuple[object, ...] | None, str]:
    if row.get("shared_opt_in") is not True:
        return None, "not-opted-in"
    if any(name not in row or row[name] is None for name in _REQUIRED):
        return None, "missing-context"
    root, cwd = row["root"], row["cwd"]
    if not isinstance(root, str) or not isinstance(cwd, str):
        return None, "invalid-path"
    try:
        root_path, cwd_path = Path(root), Path(cwd)
        if not root_path.is_absolute() or not cwd_path.is_absolute():
            return None, "invalid-path"
        root_resolved, cwd_resolved = root_path.resolve(strict=True), cwd_path.resolve(strict=True)
        cwd_resolved.relative_to(root_resolved)
        if not root_resolved.is_dir() or not cwd_resolved.is_dir():
            return None, "invalid-path"
    except (OSError, RuntimeError, ValueError):
        return None, "invalid-path"
    inputs = row["inputs"]
    if (not isinstance(inputs, (tuple, list)) or not inputs
            or any(not isinstance(x, str) or not x for x in inputs)
            or len(set(inputs)) != len(inputs)):
        return None, "invalid-inputs"
    for name in ("input_fp", "closure_fp"):
        if not isinstance(row[name], str) or not _HEX.fullmatch(row[name]):
            return None, "missing-fingerprint"
    if (not isinstance(row["cmd"], str) or not row["cmd"]
            or not isinstance(row["expected"], str) or not row["expected"]
            or row["runner_policy"] != "isolated-local-unit-v1"
            or type(row["effective_timeout"]) not in (int, float)
            or row["effective_timeout"] <= 0
            or not isinstance(row["execution_context_id"], bytes)
            or len(row["execution_context_id"]) != 32):
        return None, "invalid-context"
    key = (str(root_resolved), str(cwd_resolved), row["cmd"], row["expected"],
           tuple(inputs), row["input_fp"], row["closure_fp"], row["runner_policy"],
           row["effective_timeout"], row["execution_context_id"])
    return key, "candidate"


def plan_round(rows: Sequence[Mapping[str, object]], capability_checker: Callable[[Mapping[str, object]], bool] | None,
               *, full: bool = False, bail: bool = False, jobs: int = 1) -> list[dict]:
    """Return redacted candidate groups; never execute, persist, or grant PASS.

    Even an eligible group is only a plan, not evidence. The production runner
    currently has no verified capability provider and does not call this API.
    """
    identities = [_identity(row) for row in rows]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate participant")
    groups: list[dict] = []
    by_key: dict[tuple[object, ...], dict] = {}
    for row, (spec, number) in zip(rows, identities):
        participant = {"spec_id": spec, "row_id": number}
        key, reason = _candidate(row)
        if full or bail or jobs != 1:
            key, reason = None, "mode-requires-independent-execution"
        elif key is not None:
            try:
                capable = capability_checker is not None and capability_checker(row) is True
            except Exception:
                capable = False
            if not capable:
                key, reason = None, "capability-unavailable"
        if key is not None and key in by_key:
            by_key[key]["participants"].append(participant)
            continue
        group = {"group_id": f"group-{len(groups) + 1:04d}",
                 "participants": [participant], "eligible": key is not None,
                 "reason": reason}
        groups.append(group)
        if key is not None:
            by_key[key] = group
    return groups


def explain_round(plan: Sequence[Mapping[str, object]]) -> list[str]:
    """Explain planning decisions without including commands or context tokens."""
    return [f"{group['group_id']}: {group['reason']} ({len(group['participants'])} participant(s))"
            for group in plan]
