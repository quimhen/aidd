"""End-to-end round trip of spec 008 (T-06): the real CLI on scratch projects, the real compact page JS under node.

Flow per spec id (numeric `002-aidd-hard-rules`, non-numeric `F23-eDoc-POS`):
  aidd review -> compact review.html -> page JS (`buildReviewMd` + `saveReview` with a fake `showDirectoryPicker`
  writing into the scratch spec dir) -> review.md -> `aidd review --check/--wait/--comments` (one-line states)
  -> `aidd rules approve` refused without the consent act, accepted with a recorded tagged answer newer than review.md.
Also: `--summary` and the `Aprobar con resumen` route vs the bare Approve route, the picker/download fallbacks,
a partial save (approved: false, --check exit 2) and carry-over after editing one T-n row.

Run: python tests/e2e_review_roundtrip.py      (prints `ROUNDTRIP OK` only when every step passed)
     python -m unittest tests.e2e_review_roundtrip
Scratch projects and a scratch evidence log only; the real .aidd log, the real specs and the spec dir are never touched.
Set AIDD_E2E_KEEP=<dir> to copy the generated review.html / review.md / transcript there (real-browser evidence).

aidd:FR-304 aidd:FR-305 aidd:FR-306 aidd:FR-309 aidd:FR-310 aidd:FR-312 aidd:FR-313
"""
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "skill" / "scripts"))

import aidd_evidence as ev  # noqa: E402
import aidd_review  # noqa: E402
import aidd_rules  # noqa: E402
from tests import test_aidd_status as tas  # noqa: E402

NODE = shutil.which("node")
NUMERIC, NONNUMERIC = "002-aidd-hard-rules", "F23-eDoc-POS"
STATE_RE = re.compile(r"^STATE=(complete|pending|stale|legacy|too_many_items) approved=(\d+)/(\d+) comments=(\d+) "
                      r"stale=(yes|no) legacy=(yes|no) tag=(\[tasks:[0-9a-f]{8}\]|none)$")
TRANSCRIPT = []

HARNESS = r"""
'use strict';
const fs = require('fs'), path = require('path');
const m = require(process.argv[2]);
const job = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
function dirHandle(p) {
  return {
    async getFileHandle(name, opt) {
      const f = path.join(p, name);
      if (!fs.existsSync(f)) {
        if (!(opt && opt.create)) throw Object.assign(new Error('not found'), { name: 'NotFoundError' });
        fs.writeFileSync(f, '');
      }
      return {
        async getFile() { const b = fs.readFileSync(f); return { size: b.length, async text() { return b.toString('utf8'); } }; },
        async createWritable() {
          let buf = '';
          return { async write(t) { buf += t; }, async close() { fs.writeFileSync(f, buf); }, async abort() {} };
        }
      };
    }
  };
}
function fakeWindow(kind, rec) {
  let last = null;
  const w = {
    document: { createElement() { return { click() { rec.downloads.push({ download: this.download, type: last && last.type, text: last && last.parts.join('') }); } }; },
                body: { appendChild() {}, removeChild() {} } },
    Blob: class { constructor(parts, opts) { this.parts = parts; this.type = opts && opts.type; } },
    URL: { createObjectURL(b) { last = b; return 'blob:fake'; }, revokeObjectURL() {} }
  };
  const err = (n) => Object.assign(new Error(n), { name: n });
  if (kind === 'nopicker') return w;
  w.showDirectoryPicker = async function (opts) {
    rec.pickerCalls.push(opts || null);
    if (kind === 'abort') throw err('AbortError');
    if (kind === 'typeerror_then_ok') { if (rec.pickerCalls.length === 1) throw err('TypeError'); return dirHandle(job.dir); }
    if (kind === 'fail_both') throw err('TypeError');
    if (kind === 'other') return dirHandle(job.otherDir);
    return dirHandle(job.dir);
  };
  return w;
}
(async () => {
  if (job.op === 'build') { process.stdout.write(m.buildReviewMd(job.payload)); return; }
  if (job.op === 'missing') { process.stdout.write(m.missingSummary(job.data, job.checked)); return; }
  if (job.op === 'save') {
    const rec = { downloads: [], pickerCalls: [], statuses: [] };
    const ctx = { data: job.data, w: fakeWindow(job.kind, rec), status: (s) => rec.statuses.push(s) };
    rec.result = await m.saveReview(job.text, ctx);
    process.stdout.write(JSON.stringify(rec));
    return;
  }
  process.exit(9);
})().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
"""

EXTRA_SPEC = """
## Functional requirements

| ID | Requirement |
|---|---|
| FR-001 | Billing totals are computed per invoice |
| FR-002 | The invoices screen lists the open invoices |
| FR-003 | Voided invoices are excluded |
"""
AC_SPEC = """
## Acceptance cases

| ID | Case | Expected |
|---|---|---|
| AC-01 | One invoice | total equals the line sum |
| AC-02 | Voided invoice | not listed |
"""
VERIF = """## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `python src/check.py` | exit 0 | FR-001 |
| V-2 | `python src/check.py` | contains: totals | FR-002 |
| V-3 | `python src/check.py` | exit 0 | FR-003 |
"""


def spec_text(sid, with_ac):
    head = tas.SPEC.split("## Verification")[0].replace("# 001-x", f"# {sid}")
    return head + EXTRA_SPEC + (AC_SPEC if with_ac else "") + "\n" + VERIF


def sha8(s):
    return hashlib.sha1(s.encode()).hexdigest()[:8]


class RoundTrip(tas.Spec007Base):
    @classmethod
    def setUpClass(cls):
        if not NODE:
            return
        cls._work = tempfile.TemporaryDirectory()
        (Path(cls._work.name) / "run.js").write_text(HARNESS, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        if NODE:
            cls._work.cleanup()

    def setUp(self):
        if not NODE:
            self.skipTest("node not found: the page JS (buildReviewMd/saveReview) cannot be executed")
        super().setUp()

    # ---- helpers ------------------------------------------------------------------------------------------
    def scratch(self, sid, with_ac=None):
        with_ac = (sid == NUMERIC) if with_ac is None else with_ac
        tmp, root, d = self.project(sid, spec=spec_text(sid, with_ac))
        self.addCleanup(tmp.cleanup)
        return root, d

    def cli(self, root, *args):
        return tas.run_cli("review", *map(str, args), cwd=root)

    def gen(self, root, d):
        r = self.cli(root, d)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"(wrote|unchanged):")
        page = d / "review.html"
        return page, page.read_text(encoding="utf-8")

    @staticmethod
    def parts(html):
        js = re.search(r'<script id="aidd-js">(.*?)</script>', html, re.S).group(1)
        blob = json.loads(re.search(r'<script type="application/json" id="aidd-data">(.*?)</script>', html, re.S).group(1))
        th = re.search(r'data-tasks-hash="([0-9a-f]+)"', html).group(1)
        dg = re.search(r'data-sources-digest="([0-9a-f]+)"', html).group(1)
        return js, blob, th, dg

    def node(self, js, job):
        w = Path(self._work.name)
        (w / "page.js").write_text(js, encoding="utf-8", newline="\n")
        (w / "job.json").write_text(json.dumps(job), encoding="utf-8")
        p = subprocess.run([NODE, str(w / "run.js"), str(w / "page.js"), str(w / "job.json")],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def build_md(self, js, d, html, checked, comments=None):
        _js, blob, th, dg = self.parts(html)
        codes = blob["codes"]
        items = {c: {"approved": c in checked, "comment": (comments or {}).get(c, "")} for c in codes}
        payload = {"spec": d.name, "tasks_hash": th, "sources_digest": dg, "generated": "2026-10-05",
                   "reviewed": "2026-10-05T10:00:00", "codes": codes, "digests": blob["digests"], "items": items}
        return self.node(js, {"op": "build", "payload": payload})

    def save(self, js, d, html, text, kind, other=None):
        _js, blob, th, _dg = self.parts(html)
        data = {"spec": d.name, "tasks_hash": th, "picker_id": blob.get("picker_id")}
        out = self.node(js, {"op": "save", "kind": kind, "dir": str(d), "otherDir": str(other or d),
                             "data": data, "text": text})
        return json.loads(out)

    def one_line(self, r, code):
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), 1, f"expected ONE line, got: {r.stdout!r}")
        m = STATE_RE.match(lines[0])
        self.assertIsNotNone(m, lines[0])
        return lines[0], m

    def log(self, msg):
        TRANSCRIPT.append(msg)

    # ---- the whole owner flow, once per spec id ------------------------------------------------------------
    def flow(self, sid):
        root, d = self.scratch(sid)
        keys = aidd_review.reviewable_keys(d)

        # 1. aidd review: the real compact template
        page, html = self.gen(root, d)
        js, blob, th, dg = self.parts(html)
        self.assertEqual(re.findall(r"\{\{[A-Z0-9_]+\}\}", html), [], "unreplaced template token")
        want = base64.b64encode(hashlib.sha256(js.encode("utf-8")).digest()).decode()
        self.assertIn(f"script-src 'sha256-{want}'", html)
        self.assertEqual(blob["format"], "codes-v2")
        self.assertEqual(blob["codes"], keys)
        self.assertEqual(len(set(keys)), len(keys))
        self.assertEqual(re.findall(r'class="aidd-item"[^>]*data-code="([^"]+)"', html)
                         or re.findall(r'data-code="([^"]+)"', html), keys)     # one check per code, no more
        self.assertRegex(blob["picker_id"], r"^[A-Za-z0-9_-]{1,32}$")
        panels = re.findall(r'<section[^>]*data-tab="([a-z]+)"', html)
        expect = ["summary", "questions", "fr"] + (["ac"] if sid == NUMERIC else []) + ["tasks", "verification"]
        self.assertEqual(panels, expect)                                          # empty tabs (screens, api) absent
        self.assertNotIn("data-code=\"V-0\"", html)
        for v in ("V-1", "V-2", "V-3"):
            self.assertIn(v, keys)
        self.log(f"[{sid}] review: {len(keys)} codes, tabs={panels}, picker_id={blob['picker_id']}, CSP hash ok")
        r2 = self.cli(root, d)
        self.assertIn("unchanged:", r2.stdout)

        # 2. no review.md yet: --check says stale-or-pending in ONE line, never a paragraph
        line, m = self.one_line(self.cli(root, d, "--check"), 2)
        self.assertTrue(line.startswith("STATE=pending"), line)

        # 3. a partial save through the fake folder picker: approved: false, exit 2, one comment
        half = set(keys[: len(keys) // 2])
        commented = keys[1] if keys[1] in half else keys[0]
        text = self.build_md(js, d, html, half, {commented: "rename this helper\nand add a test"})
        self.assertIn("approved: false", text)
        self.assertIn("format: codes-v2", text)
        rec = self.save(js, d, html, text, "fs")
        self.assertEqual(rec["result"]["method"], "fs", rec)
        self.assertEqual(rec["pickerCalls"][0]["id"], blob["picker_id"])
        self.assertEqual((d / "review.md").read_text(encoding="utf-8"), text)     # written byte for byte
        parsed = aidd_review.parse_review(text)
        self.assertTrue(parsed["ok"], parsed)
        self.assertEqual(sorted(parsed["sections"]), sorted(keys))
        self.assertEqual(sum(1 for v in parsed["sections"].values() if v["approved"]), len(half))
        line, m = self.one_line(self.cli(root, d, "--check"), 2)
        self.assertEqual((m.group(1), m.group(2), m.group(3), m.group(4)),
                         ("pending", str(len(half)), str(len(keys)), "1"), line)
        self.assertEqual((m.group(5), m.group(6)), ("no", "no"))
        self.assertTrue(m.group(7).startswith("[tasks:"))
        tag = m.group(7)
        self.assertEqual(tag, self.tag(d))
        line, _ = self.one_line(self.cli(root, d, "--wait", "--timeout", "1", "--interval", "0.2"), 2)
        self.assertTrue(line.startswith("STATE=pending"))
        c = self.cli(root, d, "--comments")
        self.assertEqual(c.returncode, 0, c.stdout + c.stderr)
        self.assertEqual(c.stdout.splitlines(), [f"{commented}: rename this helper and add a test"])
        self.log(f"[{sid}] partial save: --check exit 2 '{line}'; --comments -> 1 line")
        self.assertEqual(self.review_mtime_ok(d), True)

        # 4. a --wait started BEFORE the complete save returns by itself once review.md is complete
        wait = subprocess.Popen([sys.executable, "-m", "aidd.cli", "review", str(d), "--wait", "--timeout", "60",
                                 "--interval", "0.3"], cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8",
                                env=dict(os.environ, PYTHONPATH=str(REPO), PYTHONIOENCODING="utf-8"))
        time.sleep(1.0)
        self.assertIsNone(wait.poll(), "--wait returned while the review was still partial")
        full = self.build_md(js, d, html, set(keys), {commented: "rename this helper\nand add a test"})
        self.assertIn("approved: true", full)
        rec = self.save(js, d, html, full, "fs")
        self.assertEqual(rec["result"]["method"], "fs")
        out, err = wait.communicate(timeout=60)
        self.assertEqual(wait.returncode, 0, out + err)
        lines = out.splitlines()
        self.assertEqual(len(lines), 1, out)                                      # the whole stdout is ONE line
        m = STATE_RE.match(lines[0])
        self.assertIsNotNone(m, lines[0])
        self.assertEqual(lines[0], f"STATE=complete approved={len(keys)}/{len(keys)} comments=1 stale=no legacy=no tag={tag}")
        self.assertEqual(err.strip(), "")
        self.log(f"[{sid}] --wait: {lines[0]}")
        line, _ = self.one_line(self.cli(root, d, "--check"), 0)
        self.assertEqual(line, lines[0])
        c = self.cli(root, d, "--comments")
        self.assertEqual((c.returncode, c.stdout.splitlines()), (0, [f"{commented}: rename this helper and add a test"]))
        self.assertNotIn("no comments", c.stdout)

        # 5. approve is REFUSED without the consent act (review.md alone never approves)
        tasks_before = (d / "tasks.md").read_bytes()
        r = self.approve_rc(root, d)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("review.md is complete; the owner must confirm", r.stdout)
        self.assertEqual((d / "tasks.md").read_bytes(), tasks_before)
        self.assertEqual(ev.events(root, kind="approved"), [])
        # 6. ... and accepted with a recorded tagged answer newer than review.md
        os.utime(page, (time.time() - 10, time.time() - 10))
        os.utime(d / "review.md", (time.time() - 5, time.time() - 5))
        self.prompt(root, "looks good overall")
        self.answer(root, self.aq(d), "Approve")
        r = self.approve_rc(root, d)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertRegex((d / "tasks.md").read_text(encoding="utf-8"), r"(?m)^Approved: \d{4}-\d{2}-\d{2} hash:")
        a = ev.latest_approved(root, sid)
        self.assertEqual((a["gate"], a["source"]), (2, "review+answer"))
        self.assertEqual(ev.get_gate_spec(root), sid)
        self.log(f"[{sid}] approve: refused without consent; accepted with tagged answer source={a['source']}")
        line, _ = self.one_line(self.cli(root, d, "--check"), 0)
        self.assertTrue(line.startswith("STATE=complete"))

        keep = os.environ.get("AIDD_E2E_KEEP")
        if keep:
            k = Path(keep)
            k.mkdir(parents=True, exist_ok=True)
            self.assertTrue(blob)
            shutil.copy2(page, k / f"review-{sid}.html")
            shutil.copy2(d / "review.md", k / f"review-{sid}.md")

    def review_mtime_ok(self, d):
        return (d / "review.md").stat().st_mtime >= (d / "review.html").stat().st_mtime

    def test_flow_numeric_id(self):
        self.flow(NUMERIC)

    def test_flow_non_numeric_id(self):
        self.flow(NONNUMERIC)

    # ---- save fallbacks -------------------------------------------------------------------------------------
    def test_save_fallbacks(self):
        for sid, other_sid in ((NUMERIC, NONNUMERIC), (NONNUMERIC, NUMERIC)):
            with self.subTest(sid=sid):
                root, d = self.scratch(sid)
                _page, html = self.gen(root, d)
                js, blob, th, _dg = self.parts(html)
                text = self.build_md(js, d, html, set(blob["codes"]))
                # no picker: a Blob named review.md of type application/octet-stream
                rec = self.save(js, d, html, text, "nopicker")
                self.assertEqual(rec["result"]["method"], "download")
                self.assertEqual(rec["downloads"], [{"download": "review.md", "type": "application/octet-stream",
                                                     "text": text}])
                self.assertFalse((d / "review.md").exists())
                # AbortError: silent, nothing written, no download from the page itself
                rec = self.save(js, d, html, text, "abort")
                self.assertEqual(rec["result"]["method"], "cancelled")
                self.assertEqual(rec["downloads"], [])
                self.assertEqual(rec["statuses"], [])
                self.assertFalse((d / "review.md").exists())
                # a picked folder of ANOTHER spec: nothing written anywhere
                oroot, od = self.scratch(other_sid)
                self.gen(oroot, od)
                rec = self.save(js, d, html, text, "other", other=od)
                self.assertEqual(rec["result"]["method"], "mismatch")
                self.assertTrue(any("This folder belongs to" in s and f"specs/{sid}/" in s for s in rec["statuses"]),
                                rec["statuses"])
                self.assertFalse((od / "review.md").exists())
                self.assertFalse((d / "review.md").exists())
                # a folder with no review.html at all: also refused
                empty = Path(tempfile.mkdtemp(dir=str(root)))
                rec = self.save(js, d, html, text, "other", other=empty)
                self.assertEqual(rec["result"]["method"], "mismatch")
                self.assertEqual(list(empty.iterdir()), [])
                # a TypeError on the id option retries once without it and then writes
                rec = self.save(js, d, html, text, "typeerror_then_ok")
                self.assertEqual(rec["result"]["method"], "fs")
                self.assertEqual(len(rec["pickerCalls"]), 2)
                self.assertEqual(rec["pickerCalls"][1], {"mode": "readwrite"})
                self.assertEqual((d / "review.md").read_text(encoding="utf-8"), text)
                (d / "review.md").unlink()
                # both picker calls failing: visible status line, then the download
                rec = self.save(js, d, html, text, "fail_both")
                self.assertEqual(rec["result"]["method"], "download")
                self.assertIn("Folder picker failed (TypeError): using the download instead", rec["statuses"])
                self.assertEqual(rec["downloads"][0]["download"], "review.md")
                self.assertFalse((d / "review.md").exists())
                self.log(f"[{sid}] fallbacks: nopicker->download review.md, abort->nothing, other spec->nothing, "
                         f"TypeError retry->fs, double failure->download+status")

    def test_missing_summary_and_picker_id(self):
        root, d = self.scratch(NUMERIC)
        _page, html = self.gen(root, d)
        js, blob, _th, _dg = self.parts(html)
        checked = {c: not c.startswith("V-") for c in blob["codes"]}
        out = self.node(js, {"op": "missing", "data": {"codes": blob["codes"]}, "checked": checked})
        self.assertEqual(out, "Falta: Verificación V-1..V-3")
        self.assertEqual(self.node(js, {"op": "missing", "data": {"codes": blob["codes"]},
                                        "checked": {c: True for c in blob["codes"]}}), "")

    # ---- review --summary and the two approval routes ---------------------------------------------------------
    def test_summary_and_routes(self):
        for sid in (NUMERIC, NONNUMERIC):
            with self.subTest(sid=sid):
                # --summary: mechanical text, exit 0, writes nothing, approves nothing
                root, d = self.scratch(sid)
                before = sorted(p.name for p in d.iterdir())
                r = self.cli(root, d, "--summary")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                lines = r.stdout.splitlines()
                self.assertTrue(5 <= len(lines) <= 30, lines)
                for label in ("Objective", "Scope", "Cost", "Risks"):
                    self.assertTrue(any(ln.startswith(label) for ln in lines), (label, lines))
                self.assertEqual(sorted(p.name for p in d.iterdir()), before)
                self.assertFalse((d / "review.html").exists() or (d / "review.md").exists())
                self.assertEqual(ev.events(root, kind="approved"), [])
                nt = self.cli(root, d.parent / "no-such-spec", "--summary")
                self.assertNotEqual(nt.returncode, 0)

                # bare Approve with no page: the answer route (source=answer)
                root2, d2 = self.scratch(sid)
                self.prompt(root2, "go on")
                self.answer(root2, self.aq(d2), "Approve")
                r = self.approve_rc(root2, d2)
                self.assertEqual(r.returncode, 0, r.stdout)
                self.assertEqual(ev.latest_approved(root2, sid)["source"], "answer")

                # a page exists, review.md missing: bare Approve is REFUSED, the exact summary label is accepted
                root3, d3 = self.scratch(sid)
                self.gen(root3, d3)
                os.utime(d3 / "review.html", (time.time() - 10, time.time() - 10))
                self.prompt(root3, "go on")
                self.answer(root3, self.aq(d3), "Approve")
                before3 = (d3 / "tasks.md").read_bytes()
                r = self.approve_rc(root3, d3)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertEqual((d3 / "tasks.md").read_bytes(), before3)
                self.assertEqual(ev.events(root3, kind="approved"), [])
                self.answer(root3, self.aq(d3), "Aprobar con resumen")
                r = self.approve_rc(root3, d3)
                self.assertEqual(r.returncode, 0, r.stdout)
                a = ev.latest_approved(root3, sid)
                self.assertEqual((a["gate"], a["source"]), (2, "summary"))
                self.assertFalse((d3 / "review.md").exists())                    # the summary route never writes it

                # a near-miss label never approves
                root4, d4 = self.scratch(sid)
                self.answer(root4, self.aq(d4), "aprobar con resumen")
                r = self.approve_rc(root4, d4)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertEqual(ev.events(root4, kind="approved"), [])
                self.log(f"[{sid}] --summary {len(lines)} lines, nothing written; bare Approve: no page=answer, "
                         f"page+no review.md=refused; 'Aprobar con resumen'=source summary; near miss refused")

    # ---- carry-over after editing ONE row -------------------------------------------------------------------
    def test_carry_over_after_editing_one_row(self):
        for sid in (NUMERIC, NONNUMERIC):
            with self.subTest(sid=sid):
                root, d = self.scratch(sid)
                _page, html = self.gen(root, d)
                js, blob, _th, _dg = self.parts(html)
                keys = blob["codes"]
                self.assertIn("T-02", keys)
                text = self.build_md(js, d, html, set(keys), {"FR-001": "keep me"})
                self.save(js, d, html, text, "fs")
                md_before = (d / "review.md").read_bytes()
                self.assertTrue(aidd_review.parse_review(text)["ok"])
                # edit ONE task block (the digest of T-02 changes; no total or other code does)
                t = (d / "tasks.md").read_text(encoding="utf-8")
                self.assertIn("### T-02\n", t)
                (d / "tasks.md").write_text(t.replace("### T-02\n", "### T-02\n- Note: reworded by the owner\n"),
                                            encoding="utf-8", newline="\n")
                r = self.cli(root, d)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("wrote:", r.stdout)
                _js2, blob2, _th2, _dg2 = self.parts((d / "review.html").read_text(encoding="utf-8"))
                self.assertEqual(blob2["carry"]["pending"], ["T-02"], blob2["carry"])
                self.assertEqual((blob2["carry"]["carried"], blob2["carry"]["total"]), (len(keys) - 1, len(keys)))
                self.assertEqual(sorted(blob2["prior"]), sorted(c for c in keys if c != "T-02"))
                self.assertEqual(blob2["prior"]["FR-001"], {"approved": True, "comment": "keep me"})
                self.assertEqual((d / "review.md").read_bytes(), md_before)       # regenerating never touches review.md
                self.assertIn("Arrastrados", (d / "review.html").read_text(encoding="utf-8"))
                # the old review.md is now stale against the edited tasks.md
                line, m = self.one_line(self.cli(root, d, "--check"), 3)
                self.assertTrue(line.startswith("STATE=stale"), line)
                self.log(f"[{sid}] carry-over: edited T-02 only -> pending {blob2['carry']['pending']}, "
                         f"carried {blob2['carry']['carried']}/{blob2['carry']['total']}, review.md untouched")


def main():
    if not NODE:
        print("NOTICE: node not found; the page JS steps cannot run: ROUNDTRIP SKIPPED")
        return 0
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RoundTrip)
    res = unittest.TextTestRunner(verbosity=1).run(suite)
    keep = os.environ.get("AIDD_E2E_KEEP")
    if keep and TRANSCRIPT:
        Path(keep).mkdir(parents=True, exist_ok=True)
        (Path(keep) / "e2e-transcript.txt").write_text("\n".join(TRANSCRIPT) + "\n", encoding="utf-8")
    print("\n".join(TRANSCRIPT))
    if res.wasSuccessful() and not res.skipped:
        print("ROUNDTRIP OK")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
