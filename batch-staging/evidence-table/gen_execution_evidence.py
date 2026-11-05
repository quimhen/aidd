#!/usr/bin/env python3
"""
gen_execution_evidence.py — Execution evidence table generator (AIDD R10 optimization).

Iteration 2:
- Rule 1 (literal): Exact word-boundary token match across evidence filenames and text content.
- Rule 2 (by-number): Screenshots mapped from evidence/**/s<NN>-* or SCREEN-<NN>* by the numeric part.
- Rule 3 (covers): Codes covered in spec.md Verification table by a passing V-n row recorded in
  qa-audit.md Closing gates, mapped to evidence/verify-V-n.txt as command-output.
- Unmapped codes remain strictly as not-verified candidates with reason. Never auto-verified.
- Never writes into qa-audit.md or the target repo. Stdlib-only Python.
"""

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

# Valid R10 Kinds
R10_KINDS = (
    "screenshot",
    "command-output",
    "query-result",
    "log",
    "manual-test",
    "not-verified",
)

IMG_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
TEXT_EXTENSIONS = {
    ".txt",
    ".log",
    ".out",
    ".json",
    ".md",
    ".sql",
    ".xml",
    ".html",
    ".csv",
    ".tsv",
    ".diff",
    ".patch",
}

# Directories inside spec_dir dedicated to evidence
EVIDENCE_DIR_NAMES = {"evidence", "qa-evidence", "verify", "logs", "log"}

# Files inside evidence locations that are meta/gap/plan docs rather than executed test runs
NON_EVID_PATTERNS = [
    re.compile(r"gap", re.IGNORECASE),
    re.compile(r"plan", re.IGNORECASE),
    re.compile(r"check[_-]?spec", re.IGNORECASE),
    re.compile(r"\.draft\.", re.IGNORECASE),
    re.compile(r"\.tmp\b", re.IGNORECASE),
]


def _clean_cell(cell: str) -> str:
    """Trim markdown formatting (backticks, whitespace) from a cell."""
    return cell.strip().strip("`").strip()


def _norm_v_id(vid: str) -> str:
    """Normalize check identifier: 'V-1', 'V-01', 'v1' -> 'V-1'."""
    m = re.search(r"(\d+)", vid)
    if m:
        num = int(m.group(1))
        return f"V-{num}"
    return vid.strip().upper()


def _is_code_candidate(code: str) -> bool:
    """Check if code is one of the executable targets requiring R10 evidence:
    SCREEN-nn, SCREEN-nn-Fnn, API-nnn, -Fnn, T-nn.
    Components (COMP-nn) do not require execution evidence.
    """
    c = code.upper()
    if c.startswith("COMP-"):
        return False
    if re.match(r"^SCREEN-\d+", c):
        return True
    if re.match(r"^API-\d+", c):
        return True
    if re.match(r"^T-\d+", c):
        return True
    if re.search(r"-F\d+$", c):
        return True
    return False


def _is_status_done(status: str) -> bool:
    """Check if row status in Mapping ledger indicates completed/implemented."""
    s = status.strip()
    if "\u2705" in s or "\u2611" in s or "PASS" in s.upper():
        return True
    upper = s.upper()
    if "IMPLEMENTED" in upper or "DONE" in upper or "COVERED" in upper:
        if "NOT" in upper or "PARTIAL" in upper or "FAIL" in upper:
            return False
        return True
    return False


def parse_qa_audit(qa_path: Path):
    """Parse qa-audit.md to extract required codes and exemptions.
    Returns:
        required_codes: list of dicts: {'code': str, 'status': str, 'target_file': str}
        exempt_codes: set of str
    """
    if not qa_path.exists():
        return [], set()

    text = qa_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    exempt_codes = set()
    in_exempt = False
    for line in lines:
        stripped = line.strip()
        if re.search(r"^##+\s*Open\s+exceptions\b", stripped, re.IGNORECASE):
            in_exempt = True
            continue
        if in_exempt:
            if stripped.startswith("##"):
                in_exempt = False
            elif stripped.startswith("|") and not stripped.startswith("|---"):
                tokens = re.findall(r"\b[A-Z]+-\d+(?:-F\d+)?\b", stripped)
                exempt_codes.update(tokens)

    # Locate Mapping ledger or Status table
    in_ledger = False
    header_indices = {}
    required_codes = []

    for line in lines:
        stripped = line.strip()
        if re.search(r"^##+\s*(Mapping\s+ledger|Status)\b", stripped, re.IGNORECASE):
            in_ledger = True
            header_indices = {}
            continue

        if in_ledger:
            if stripped.startswith("##"):
                break
            if not stripped.startswith("|"):
                continue

            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if not cells:
                continue

            if not header_indices:
                for idx, c in enumerate(cells):
                    name = c.lower()
                    if "code" in name:
                        header_indices["code"] = idx
                    elif "status" in name:
                        header_indices["status"] = idx
                    elif "evidence" in name or "target" in name or "file" in name:
                        header_indices.setdefault("target", idx)
                continue

            # Skip separator line
            if all(set(c.replace(":", "").replace("-", "").strip()) == set() for c in cells if c):
                continue

            code_idx = header_indices.get("code", 0)
            status_idx = header_indices.get("status", 1)
            target_idx = header_indices.get("target", 2 if len(cells) > 2 else None)

            if code_idx >= len(cells):
                continue

            raw_code = _clean_cell(cells[code_idx])
            raw_status = cells[status_idx] if status_idx < len(cells) else ""
            raw_target = _clean_cell(cells[target_idx]) if target_idx is not None and target_idx < len(cells) else ""

            if not raw_code:
                continue

            if _is_code_candidate(raw_code) and _is_status_done(raw_status):
                if raw_code not in exempt_codes:
                    required_codes.append({
                        "code": raw_code,
                        "status": raw_status.strip(),
                        "target_file": raw_target,
                    })

    return required_codes, exempt_codes


def parse_closing_gates(qa_path: Path):
    """Parse qa-audit.md Closing gates table to find passed verification runs.
    A run counts as passed only if Result contains 'PASS' (never inferred from log).
    Returns dict: norm_v_id -> {'raw_id': str, 'result': str, 'evidence': str}
    """
    if not qa_path.exists():
        return {}

    text = qa_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"###?\s*Closing\s+gates.*?(?=\n###?|\n## |\Z)", text, re.DOTALL | re.IGNORECASE)
    if not m:
        return {}

    lines = m.group(0).splitlines()
    header_indices = {}
    passed_runs = {}

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [_clean_cell(c) for c in stripped.split("|")[1:-1]]
        if not cells:
            continue

        if not header_indices:
            for idx, c in enumerate(cells):
                name = c.lower().strip()
                if name in ("#", "id", "gate", "check", "check #", "gate #") or name.startswith("#"):
                    header_indices["id"] = idx
                elif "result" in name or "status" in name:
                    header_indices["result"] = idx
                elif "evidence" in name:
                    header_indices["evidence"] = idx
            continue

        if all(set(c.replace(":", "").replace("-", "").strip()) == set() for c in cells if c):
            continue

        id_idx = header_indices.get("id", 0)
        res_idx = header_indices.get("result", 3 if len(cells) > 3 else 1)
        ev_idx = header_indices.get("evidence", 4 if len(cells) > 4 else None)

        if id_idx < len(cells) and res_idx < len(cells):
            raw_id = cells[id_idx].strip()
            res_val = cells[res_idx].strip().upper()
            ev_val = cells[ev_idx].strip() if ev_idx is not None and ev_idx < len(cells) else ""

            # Check if recorded as passed by aidd
            if "PASS" in res_val and "FAIL" not in res_val:
                norm_id = _norm_v_id(raw_id)
                passed_runs[norm_id] = {
                    "raw_id": raw_id,
                    "result": res_val,
                    "evidence": ev_val,
                }

    return passed_runs


def parse_verification_table(spec_path: Path):
    """Parse spec.md '## Verification' table.
    Expands covered codes (handling ranges like FR-001..FR-015, T-167 to T-184, and individual codes).
    Returns dict: norm_v_id -> {'raw_id': str, 'codes': set of str, 'raw_covers': str}
    """
    if not spec_path.exists():
        return {}

    text = spec_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"##\s*Verification.*?(?=\n## |\Z)", text, re.DOTALL | re.IGNORECASE)
    if not m:
        return {}

    lines = m.group(0).splitlines()
    header_indices = {}
    v_rows = {}

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [_clean_cell(c) for c in stripped.split("|")[1:-1]]
        if not cells:
            continue

        if not header_indices:
            for idx, c in enumerate(cells):
                name = c.lower().strip()
                if name in ("#", "id", "gate", "check", "check #", "gate #") or name.startswith("#"):
                    header_indices["id"] = idx
                elif "covers" in name or "cover" in name:
                    header_indices["covers"] = idx
                elif "command" in name:
                    header_indices["cmd"] = idx
            continue

        if all(set(c.replace(":", "").replace("-", "").strip()) == set() for c in cells if c):
            continue

        id_idx = header_indices.get("id", 0)
        cov_idx = header_indices.get("covers", len(cells) - 1)

        if id_idx < len(cells) and cov_idx < len(cells):
            raw_id = cells[id_idx].strip()
            covers_text = cells[cov_idx].strip()
            codes = set()

            # 1. Expand code ranges (e.g. FR-001..FR-015, FR-001..015, T-167 to T-184)
            for r_match in re.finditer(
                r"\b([A-Z]+)-(\d+)\s*(?:\.\.|to)\s*(?:[A-Z]+-)?(\d+)\b", covers_text, re.IGNORECASE
            ):
                prefix = r_match.group(1).upper()
                s_str, e_str = r_match.group(2), r_match.group(3)
                pad = len(s_str)
                try:
                    for num in range(int(s_str), int(e_str) + 1):
                        codes.add(f"{prefix}-{num:0{pad}d}")
                except Exception:
                    pass

            # 2. Individual code tokens (SCREEN-nn, API-nnn, T-nn, FR-nnn, AC-nnn, etc.)
            for c_match in re.finditer(r"\b([A-Z]+-\d+(?:-F\d+)?)\b", covers_text, re.IGNORECASE):
                codes.add(c_match.group(1).upper())

            norm_id = _norm_v_id(raw_id)
            v_rows[norm_id] = {
                "raw_id": raw_id,
                "codes": codes,
                "raw_covers": covers_text,
            }

    return v_rows


def find_v_evidence_file(norm_v_id: str, spec_dir: Path, closing_gate_ev: str = "") -> Path:
    """Find the concrete evidence file on disk for a V-n check."""
    spec_dir = spec_dir.resolve()
    # 1. From closing gate evidence column if present
    if closing_gate_ev:
        clean_ev = closing_gate_ev.strip().strip("`").strip()
        p = spec_dir / clean_ev
        if p.is_file():
            return p

    # 2. Check standard patterns in spec_dir / evidence
    m = re.search(r"(\d+)", norm_v_id)
    v_num = m.group(1) if m else ""

    candidates = [
        spec_dir / "evidence" / f"verify-{norm_v_id}.txt",
        spec_dir / "evidence" / f"verify-V-{v_num}.txt",
        spec_dir / "evidence" / f"verify-{v_num}.txt",
        spec_dir / "evidence" / f"verify-{norm_v_id}.log",
        spec_dir / "evidence" / f"verify-V-{v_num}.log",
        spec_dir / "evidence" / f"verify-{v_num}.log",
        spec_dir / "evidence" / f"verify-{norm_v_id}.out",
        spec_dir / "evidence" / f"verify-V-{v_num}.out",
        spec_dir / "evidence" / f"verify-{v_num}.out",
    ]
    for c in candidates:
        if c.is_file():
            return c

    # 3. Check any file in evidence directory matching verify-V-{v_num} or verify-{v_num}
    ev_dir = spec_dir / "evidence"
    if ev_dir.is_dir():
        for f in ev_dir.iterdir():
            if f.is_file() and (
                f.name.startswith(f"verify-V-{v_num}.") or f.name.startswith(f"verify-{v_num}.")
            ):
                return f

    return None


def find_evidence_files(spec_dir: Path):
    """Find all candidate evidence files inside the spec's evidence locations:
    - evidence/ (recursive)
    - qa-evidence/ (recursive)
    - verify/ (recursive)
    - logs/ or log/ (recursive)
    - root of spec_dir matching *.png, *.jpg, *.jpeg, *.webp, *.log
    """
    candidate_files = []
    spec_dir = spec_dir.resolve()

    for item in spec_dir.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(spec_dir)
        parts = rel.parts

        # Top-level evidence directories
        if parts[0].lower() in EVIDENCE_DIR_NAMES:
            candidate_files.append(item)
        # Spec-root image or log files
        elif len(parts) == 1 and item.suffix.lower() in IMG_EXTENSIONS | {".log"}:
            candidate_files.append(item)

    return candidate_files


def is_non_evidence_meta_file(file_path: Path) -> bool:
    """Filter out gap reports, check_spec output, and planning files that are not executed evidence."""
    name = file_path.name
    for pat in NON_EVID_PATTERNS:
        if pat.search(name):
            return True
    return False


def classify_kind(file_path: Path, content: str = "") -> str:
    """Classify R10 Kind:
    - screenshot: image files (.png, .jpg, .jpeg, .webp)
    - log: .log extension
    - query-result: .sql, db query results, psql / pgTAP execution outputs
    - command-output: .txt, .out, terminal / test execution outputs
    """
    ext = file_path.suffix.lower()
    if ext in IMG_EXTENSIONS:
        return "screenshot"
    if ext == ".log":
        return "log"

    lower_name = file_path.name.lower()
    if ext == ".sql" or "psql" in lower_name or "query" in lower_name or "db_verify" in lower_name:
        return "query-result"

    if content:
        c_head = content[:1500].lower()
        if "rows affected" in c_head or "select " in c_head or "pgtap" in c_head:
            return "query-result"
        if (
            "test" in lower_name
            or "verify" in lower_name
            or ext in (".txt", ".out")
            or c_head.startswith("# ")
            or "exit 0" in c_head
            or "pass" in c_head
        ):
            return "command-output"

    return "command-output"


def match_code_in_file(code: str, file_path: Path, spec_dir: Path):
    """Check if file mentions code literally with word boundaries.
    Returns (matched: bool, match_source: str, content: str)
    """
    pat = re.compile(r"\b" + re.escape(code) + r"\b", re.IGNORECASE)

    # Check filename / relative path
    rel_path_str = str(file_path.relative_to(spec_dir)).replace("\\", "/")
    if pat.search(file_path.name) or pat.search(rel_path_str):
        content = ""
        if file_path.suffix.lower() in TEXT_EXTENSIONS:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
        return True, "filename", content

    # Check text content
    if file_path.suffix.lower() in TEXT_EXTENSIONS:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if pat.search(content):
                return True, "content", content
        except Exception:
            pass

    return False, "", ""


def score_evidence_match(code: str, file_path: Path, match_source: str, kind: str, content: str) -> int:
    """Score matching evidence files for literal matching:
    - For SCREEN-* codes: screenshots get highest priority.
    - Filename match > content match.
    - Prefer loaded/admin/desktop (1280).
    - Prefer executed test files (verify-V, test) with PASS/ok.
    """
    score = 0
    c_upper = code.upper()
    is_screen = c_upper.startswith("SCREEN-")
    name_lower = file_path.name.lower()

    if is_screen:
        if kind == "screenshot":
            score += 1000
            if "loaded" in name_lower:
                score += 50
            if "1280" in name_lower:
                score += 20
            if "admin" in name_lower:
                score += 10
            if "empty" in name_lower:
                score += 5
        else:
            score += 100
    else:
        if kind in ("command-output", "query-result", "log"):
            score += 500

    if match_source == "filename":
        score += 200

    if "verify-v" in name_lower or "test" in name_lower:
        score += 50

    if content:
        if "pass" in content.lower() or "ok" in content.lower() or "\u2713" in content:
            score += 30

    return score


def score_screenshot_match(code: str, file_path: Path, rel_path: str) -> int:
    """Score candidate screenshot files for by-number matching:
    - Prefer captured app screenshot (app.png).
    - Prefer loaded / ready state.
    - Prefer standard viewport (1280).
    - Prefer admin / aprobador views.
    - Demote mockups and side-by-side pair diffs.
    """
    score = 1000
    p_lower = rel_path.lower()
    name_lower = file_path.name.lower()

    if "app.png" in name_lower:
        score += 80
    if "loaded" in p_lower or "loaded" in name_lower:
        score += 60
    if "1280" in p_lower or "1280" in name_lower:
        score += 30
    if "admin" in p_lower or "aprobador" in p_lower or "desktop" in p_lower:
        score += 15
    if "empty" in p_lower:
        score += 10
    if "mockup" in p_lower:
        score -= 50
    if "pair" in p_lower:
        score -= 40
    if "diff" in p_lower:
        score -= 30

    return score


def check_freshness(spec_dir: Path, evidence_path: Path, target_file_hint: str = ""):
    """Check whether the evidence file is older than the newest target code file (best effort).
    Returns: (is_stale: bool, message: str)
    """
    spec_dir = spec_dir.resolve()
    project_root = None
    cur = spec_dir
    while cur.parent != cur:
        if cur.name.lower() == "specs":
            project_root = cur.parent
            break
        if (cur / ".git").exists() or (cur / ".aidd").exists():
            project_root = cur
            break
        cur = cur.parent

    if project_root is None:
        project_root = spec_dir.parent

    code_files = []
    if target_file_hint:
        hint_clean = target_file_hint.strip().strip("`").strip()
        p = project_root / hint_clean
        if p.is_file():
            code_files.append(p)

    tasks_path = spec_dir / "tasks.md"
    if tasks_path.exists():
        try:
            tasks_txt = tasks_path.read_text(encoding="utf-8", errors="ignore")
            matches = re.findall(r"[`']?([A-Za-z0-9_/-]+\.(?:ts|tsx|py|sql|js|jsx|cs))[`']?", tasks_txt)
            for m in matches:
                p = project_root / m
                if p.is_file() and p not in code_files:
                    code_files.append(p)
        except Exception:
            pass

    if not code_files:
        return False, "no target code files found on disk to compare against (freshness check advisory only)"

    newest_code_file = max(code_files, key=lambda f: f.stat().st_mtime)
    code_mtime = newest_code_file.stat().st_mtime
    ev_mtime = evidence_path.stat().st_mtime

    if ev_mtime < code_mtime:
        ev_dt = datetime.datetime.fromtimestamp(ev_mtime, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        code_dt = datetime.datetime.fromtimestamp(code_mtime, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        rel_code = str(newest_code_file.relative_to(project_root)).replace("\\", "/")
        return True, f"evidence ({ev_dt}) is older than newest target code file {rel_code} ({code_dt})"

    return False, "evidence is newer than target code files"


def generate_execution_evidence(spec_dir: Path, include_meta_files: bool = False):
    """Core analysis: reads spec qa-audit.md and spec.md, evaluates evidence files,
    and applies mapping rules in strict precedence:
    1. literal: exact token match in candidate evidence files
    2. by-number: for SCREEN-* codes, screenshot matching s<NN>-* or SCREEN-<NN>* by number
    3. covers: code covered by a passing V-n run in qa-audit.md Closing gates with file on disk
    4. unmapped: candidate for not-verified with reason
    """
    spec_dir = spec_dir.resolve()
    qa_path = spec_dir / "qa-audit.md"
    spec_path = spec_dir / "spec.md"

    if not qa_path.exists():
        raise FileNotFoundError(f"qa-audit.md not found in {spec_dir}")

    required_codes, exempt_codes = parse_qa_audit(qa_path)
    evidence_files = find_evidence_files(spec_dir)
    v_rows = parse_verification_table(spec_path)
    passed_gates = parse_closing_gates(qa_path)

    mapped_rows = []
    unmapped_codes = []
    freshness_warnings = []

    for req in required_codes:
        code = req["code"]
        target_hint = req.get("target_file", "")
        code_upper = code.upper()
        is_screen = code_upper.startswith("SCREEN-")

        # --- Rule 1: Literal token mapping ---
        lit_candidates = []
        for ef in evidence_files:
            if not include_meta_files and is_non_evidence_meta_file(ef):
                continue
            matched, source, content = match_code_in_file(code, ef, spec_dir)
            if matched:
                kind = classify_kind(ef, content)
                score = score_evidence_match(code, ef, source, kind, content)
                lit_candidates.append({
                    "file": ef,
                    "rel_path": str(ef.relative_to(spec_dir)).replace("\\", "/"),
                    "kind": kind,
                    "source": source,
                    "content": content,
                    "score": score,
                    "method": "literal",
                })

        if lit_candidates:
            lit_candidates.sort(key=lambda c: (-c["score"], len(c["rel_path"]), c["rel_path"]))
            best = lit_candidates[0]
            is_stale, f_msg = check_freshness(spec_dir, best["file"], target_hint)
            if is_stale:
                freshness_warnings.append({"code": code, "evidence": best["rel_path"], "message": f_msg})
            mapped_rows.append({
                "code": code,
                "kind": best["kind"],
                "evidence": best["rel_path"],
                "verified_by": "agent",
                "method": "literal",
                "match_source": best["source"],
                "is_stale": is_stale,
            })
            continue

        # --- Rule 2: Screenshot by-number (for SCREEN-* codes) ---
        if is_screen:
            m_num = re.match(r"^SCREEN-0*(\d+)", code, re.IGNORECASE)
            if m_num:
                num = m_num.group(1)
                pat_s = re.compile(rf"(?:^|[\\/])s0*{num}(?:[-_\\/]|$)", re.IGNORECASE)
                pat_screen = re.compile(rf"\bSCREEN-0*{num}\b", re.IGNORECASE)
                num_candidates = []

                for ef in evidence_files:
                    if ef.suffix.lower() not in IMG_EXTENSIONS:
                        continue
                    if not include_meta_files and is_non_evidence_meta_file(ef):
                        continue
                    rel_p = str(ef.relative_to(spec_dir)).replace("\\", "/")
                    if pat_s.search(rel_p) or pat_screen.search(rel_p):
                        score = score_screenshot_match(code, ef, rel_p)
                        num_candidates.append({
                            "file": ef,
                            "rel_path": rel_p,
                            "kind": "screenshot",
                            "score": score,
                            "method": "by-number",
                        })

                if num_candidates:
                    num_candidates.sort(key=lambda c: (-c["score"], len(c["rel_path"]), c["rel_path"]))
                    best = num_candidates[0]
                    is_stale, f_msg = check_freshness(spec_dir, best["file"], target_hint)
                    if is_stale:
                        freshness_warnings.append({"code": code, "evidence": best["rel_path"], "message": f_msg})
                    mapped_rows.append({
                        "code": code,
                        "kind": "screenshot",
                        "evidence": best["rel_path"],
                        "verified_by": "agent",
                        "method": "by-number",
                        "match_source": "by-number",
                        "is_stale": is_stale,
                    })
                    continue

        # --- Rule 3: Verification Covers table ---
        found_cover = False
        for norm_id, v_data in v_rows.items():
            if code_upper in v_data["codes"]:
                # Must have recorded passing verify run in qa-audit.md Closing gates
                if norm_id in passed_gates:
                    # Evidence file must exist on disk
                    ev_f = find_v_evidence_file(norm_id, spec_dir, passed_gates[norm_id].get("evidence", ""))
                    if ev_f and ev_f.is_file():
                        rel_ev = str(ev_f.relative_to(spec_dir)).replace("\\", "/")
                        is_stale, f_msg = check_freshness(spec_dir, ev_f, target_hint)
                        if is_stale:
                            freshness_warnings.append({"code": code, "evidence": rel_ev, "message": f_msg})
                        mapped_rows.append({
                            "code": code,
                            "kind": "command-output",
                            "evidence": rel_ev,
                            "verified_by": "agent",
                            "method": "covers",
                            "match_source": f"covers:{v_data['raw_id']}",
                            "is_stale": is_stale,
                        })
                        found_cover = True
                        break

        if found_cover:
            continue

        # --- Unmapped candidate ---
        meta_matches = []
        if not include_meta_files:
            for ef in evidence_files:
                if is_non_evidence_meta_file(ef):
                    m, _, _ = match_code_in_file(code, ef, spec_dir)
                    if m:
                        meta_matches.append(ef.name)

        if meta_matches:
            reason = f"mentioned only in non-executed meta/gap files ({', '.join(meta_matches[:2])})"
        else:
            reason = "no evidence file mentions code and not covered by a passing Verification gate"

        unmapped_codes.append({
            "code": code,
            "status": req.get("status", ""),
            "reason": reason,
        })

    method_counts = {}
    for r in mapped_rows:
        m = r.get("method", "literal")
        method_counts[m] = method_counts.get(m, 0) + 1

    summary = {
        "spec_name": spec_dir.name,
        "spec_dir": str(spec_dir),
        "total_codes": len(required_codes),
        "mapped_count": len(mapped_rows),
        "mapped_by_literal": method_counts.get("literal", 0),
        "mapped_by_covers": method_counts.get("covers", 0),
        "mapped_by_number": method_counts.get("by-number", 0),
        "unmapped_count": len(unmapped_codes),
        "exempt_count": len(exempt_codes),
        "freshness_warnings_count": len(freshness_warnings),
    }

    return {
        "summary": summary,
        "mapped_rows": mapped_rows,
        "unmapped_codes": unmapped_codes,
        "freshness_warnings": freshness_warnings,
        "exempt_codes": sorted(list(exempt_codes)),
    }


def format_markdown_proposal(result: dict) -> str:
    """Format the proposal into a clean markdown document."""
    s = result["summary"]
    mapped = result["mapped_rows"]
    unmapped = result["unmapped_codes"]
    freshness = result["freshness_warnings"]

    md = []
    md.append(f"# Execution Evidence Proposal — {s['spec_name']}")
    md.append("")
    md.append("Generated by `gen_execution_evidence.py` (AIDD R10 stdlib tool). Dry-run proposal only.")
    md.append("")
    md.append("## Coverage summary")
    md.append(f"- **Total codes requiring evidence**: {s['total_codes']}")
    md.append(f"- **Mapped automatically**: {s['mapped_count']}")
    md.append(f"  - by literal token: {s.get('mapped_by_literal', 0)}")
    md.append(f"  - by verification covers: {s.get('mapped_by_covers', 0)}")
    md.append(f"  - by number (screenshots): {s.get('mapped_by_number', 0)}")
    md.append(f"- **Unmapped**: {s['unmapped_count']}")
    if s["exempt_count"] > 0:
        md.append(f"- **Exempt (Open Exceptions)**: {s['exempt_count']}")
    if s["freshness_warnings_count"] > 0:
        md.append(f"- **Freshness warnings (best effort)**: {s['freshness_warnings_count']}")
    md.append("")

    # R10 Table with Method audit column
    md.append("## Execution evidence")
    md.append("")
    md.append("| Code | Kind | Evidence | Verified by | Method |")
    md.append("|---|---|---|---|---|")
    if mapped:
        for r in mapped:
            md.append(f"| {r['code']} | {r['kind']} | {r['evidence']} | {r['verified_by']} | {r['method']} |")
    else:
        md.append("| - | - | - | - | - |")
    md.append("")

    if unmapped:
        md.append("## Unmapped codes (candidates for `not-verified`)")
        md.append("")
        md.append("> [!IMPORTANT]")
        md.append("> Unmapped codes are NOT verified. To mark them `not-verified` under rule R10:")
        md.append("> 1. Create a human test script (e.g. `specs/<id>/human-test-<code_id>.md`).")
        md.append("> 2. Change the code's Status in Mapping ledger to `⚠️ PARTIAL`.")
        md.append("> 3. Never auto-label unmapped codes as verified.")
        md.append("")
        md.append("| Code | Mapping ledger Status | Reason unmapped | Candidate action |")
        md.append("|---|---|---|---|")
        for u in unmapped:
            md.append(f"| {u['code']} | {u['status']} | {u['reason']} | `not-verified` candidate |")
        md.append("")

    if freshness:
        md.append("## Freshness warnings (best effort)")
        md.append("")
        for f in freshness:
            md.append(f"- **{f['code']}** ({f['evidence']}): {f['message']}")
        md.append("")

    return "\n".join(md)


def audit_existing_kinds(qa_path: Path):
    """Audit existing Execution evidence table in qa-audit.md for invalid kinds (e.g. 'command')."""
    if not qa_path.exists():
        return []

    text = qa_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"##\s*Execution evidence.*?(?=\n## |\Z)", text, re.DOTALL | re.IGNORECASE)
    if not m:
        return []

    lines = m.group(0).splitlines()
    header_indices = {}
    invalid_rows = []

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [_clean_cell(c) for c in stripped.split("|")[1:-1]]
        if not cells:
            continue

        if not header_indices:
            for idx, c in enumerate(cells):
                name = c.lower().strip()
                if "code" in name:
                    header_indices["code"] = idx
                elif "kind" in name:
                    header_indices["kind"] = idx
                elif "evidence" in name:
                    header_indices["evidence"] = idx
            continue

        if all(set(c.replace(":", "").replace("-", "").strip()) == set() for c in cells if c):
            continue

        kind_idx = header_indices.get("kind", 1)
        code_idx = header_indices.get("code", 0)
        ev_idx = header_indices.get("evidence", 2)

        if kind_idx < len(cells):
            kind_val = cells[kind_idx].strip()
            code_val = cells[code_idx].strip() if code_idx < len(cells) else ""
            ev_val = cells[ev_idx].strip() if ev_idx < len(cells) else ""
            if kind_val and kind_val not in R10_KINDS:
                # Propose corrected Kind
                proposed = "command-output" if kind_val == "command" else "not-verified"
                invalid_rows.append({
                    "code": code_val,
                    "invalid_kind": kind_val,
                    "proposed_kind": proposed,
                    "evidence": ev_val,
                })

    return invalid_rows


def main():
    parser = argparse.ArgumentParser(
        description="Propose the '## Execution evidence' table for qa-audit.md from existing files (AIDD R10)."
    )
    parser.add_argument("spec_dir", help="Path to the specification directory")
    parser.add_argument("--out", "-o", help="Output file path (default: stdout)")
    parser.add_argument("--check", action="store_true", help="Exit 1 if unmapped codes exist, 0 if all mapped")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run mode (default: True, never modifies files)")
    parser.add_argument("--include-meta", action="store_true", help="Include gap reports/plans in evidence scan (default: False)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    spec_path = Path(args.spec_dir)
    if not spec_path.is_dir():
        sys.stderr.write(f"Error: spec_dir '{args.spec_dir}' is not a directory.\n")
        sys.exit(2)

    try:
        result = generate_execution_evidence(spec_path, include_meta_files=args.include_meta)
    except Exception as e:
        sys.stderr.write(f"Error processing spec: {e}\n")
        sys.exit(2)

    if args.json:
        output_text = json.dumps(result, indent=2)
    else:
        output_text = format_markdown_proposal(result)

    if args.out:
        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(output_text, encoding="utf-8")
        sys.stderr.write(f"Wrote proposal to {args.out}\n")
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(output_text)

    if args.check:
        unmapped_count = result["summary"]["unmapped_count"]
        if unmapped_count > 0:
            sys.stderr.write(f"Check failed: {unmapped_count} unmapped code(s) exist.\n")
            sys.exit(1)
        sys.stderr.write("Check passed: all codes mapped.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
