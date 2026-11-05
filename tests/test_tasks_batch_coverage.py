"""One spec may split its tasks over `tasks.md` + batch files `tasks-<name>.md` (e.g. one per amendment
batch). The approval hash (R6), R1, check_spec, the code gate state and `aidd review` must cover ALL of
them; a spec WITHOUT batch files keeps exactly the same hash (backward compatible: approvals stay valid)."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import aidd_rules as R  # noqa: E402
import aidd_review as RV  # noqa: E402
import aidd_status  # noqa: E402


def blk(n, agent, role="builder"):
    return (f"### T-{n:02d}\n- Agent min: {agent}\n- Human ref hours: 2\n- Tokens (est): 10k\n"
            f"- Agent role: {role}\n- Model tier: medium\n\n")


def tasks_text(ids, agent=10, total=None, approved="Approved: PENDING", extra=""):
    blocks = "".join(blk(i, agent) for i in ids)
    rows = "".join(f"| {k} | T-{i:02d} | builder | {agent} | 10 | 2 |\n" for k, i in enumerate(ids, 1))
    total = agent * len(ids) if total is None else total
    return (f"# Tasks\n\n{blocks}## Waves\n\n| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |\n"
            f"|---|---|---|---|---|---|\n{rows}\nTotal agent time (critical path): {total} min\n"
            f"Total tokens (k): {10 * len(ids)}\n{extra}\n{approved}\n")


BASE = tasks_text([1, 2])
BATCH = tasks_text([3, 4], approved="")
# sha1[:12] of the approval projection of BASE: the compat pin (identical to approval_hash on HEAD)
BASE_HASH_PIN = hashlib.sha1(R.approval_projection(BASE).encode("utf-8")).hexdigest()[:12]


def make_spec(tmp, batches=None, base=BASE):
    d = Path(tmp) / "specs" / "001-x"
    d.mkdir(parents=True)
    (d / "spec.md").write_text("# spec\n", encoding="utf-8")
    (d / "tasks.md").write_text(base, encoding="utf-8", newline="")
    for name, text in (batches or {}).items():
        (d / name).write_text(text, encoding="utf-8", newline="")
    return d


class TestBatchNames(unittest.TestCase):
    def test_only_tasks_dash_name_md_sorted(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t, {"tasks-b.md": BATCH, "tasks-amendment-03.md": BATCH, "tasks-detail.draft.md": "x",
                              "tasks.draft.md": "x", "tasks-x.txt": "x", "tasks-.md": "x"})
            self.assertEqual(R.tasks_batch_names(d), ["tasks-amendment-03.md", "tasks-b.md"])

    def test_no_batches(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(R.tasks_batch_names(make_spec(t)), [])


class TestHashCompat(unittest.TestCase):
    def test_spec_without_batches_keeps_the_exact_hash(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t)
            combined = R.with_batches(d, BASE)
            self.assertEqual(combined, BASE)  # byte identical text -> identical hash
            self.assertEqual(R.approval_hash(combined), R.approval_hash(BASE))
            self.assertEqual(R.approval_hash(combined), BASE_HASH_PIN)

    def test_missing_base_stays_empty(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(R.with_batches(Path(t), ""), "")


class TestHashCoversBatches(unittest.TestCase):
    def h(self, d):
        return R.approval_hash(R.with_batches(d, (d / "tasks.md").read_text(encoding="utf-8")))

    def test_batch_changes_hash_and_edit_changes_it_again(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t)
            h0 = self.h(d)
            (d / "tasks-amendment-03.md").write_text(BATCH, encoding="utf-8")
            h1 = self.h(d)
            self.assertNotEqual(h0, h1)
            (d / "tasks-amendment-03.md").write_text(BATCH.replace("Agent min: 10", "Agent min: 11", 1), encoding="utf-8")
            self.assertNotEqual(h1, self.h(d))

    def test_order_is_deterministic_by_name_not_by_creation(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            da = make_spec(a, {"tasks-a.md": BATCH, "tasks-b.md": BASE})
            db = Path(b) / "specs" / "001-x"
            db.mkdir(parents=True)
            (db / "tasks.md").write_text(BASE, encoding="utf-8", newline="")
            (db / "tasks-b.md").write_text(BASE, encoding="utf-8")
            (db / "tasks-a.md").write_text(BATCH, encoding="utf-8")
            self.assertEqual(self.h(da), self.h(db))

    def test_crlf_does_not_change_the_hash(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t, {"tasks-a.md": BATCH})
            h1 = self.h(d)
            (d / "tasks-a.md").write_bytes(BATCH.replace("\n", "\r\n").encode("utf-8"))
            self.assertEqual(h1, self.h(d))

    def test_approval_valid_then_void_after_batch_edit(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t, {"tasks-a.md": BATCH})
            full = R.with_batches(d, BASE)
            h = R.approval_hash(full)
            (d / "tasks.md").write_text(BASE.replace("Approved: PENDING", f"Approved: 2026-11-05 hash:{h}"), encoding="utf-8")
            vs = R.check_spec_dir(d, static_only=True)
            self.assertFalse([v for v in vs if v["rule"] == "R6"], vs)
            (d / "tasks-a.md").write_text(BATCH.replace("Human ref hours: 2", "Human ref hours: 3", 1), encoding="utf-8")
            vs = R.check_spec_dir(d, static_only=True)
            self.assertTrue([v for v in vs if v["rule"] == "R6" and "changed after approval" in v["message"]], vs)

    def test_approved_line_inside_a_batch_voids_the_approval(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t, {"tasks-a.md": BATCH + "\nApproved: 2026-11-05 hash:abcdefabcdef\n"})
            vs = R.check_spec_dir(d, static_only=True)
            self.assertTrue([v for v in vs if v["rule"] == "R6"], vs)


class TestR1PerFile(unittest.TestCase):
    def test_good_batch_passes(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t, {"tasks-a.md": BATCH})
            self.assertFalse([v for v in R.check_spec_dir(d, static_only=True) if v["rule"] == "R1"])

    def test_bad_wave_total_in_a_batch_is_reported_with_its_file(self):
        bad = tasks_text([3, 4], total=999, approved="")
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t, {"tasks-a.md": bad})
            vs = [v for v in R.check_spec_dir(d, static_only=True) if v["rule"] == "R1"]
            self.assertTrue([v for v in vs if "tasks-a.md" in v["message"] and "Total" in v["message"]], vs)

    def test_same_task_in_two_files_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t, {"tasks-a.md": tasks_text([2, 5], approved="")})
            vs = [v for v in R.check_spec_dir(d, static_only=True) if v["rule"] == "R1"]
            self.assertTrue([v for v in vs if "T-02" in v["message"] and "more than one" in v["message"]], vs)

    def test_batch_without_waves_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t, {"tasks-a.md": "# batch\n\n" + blk(3, 10)})
            vs = [v for v in R.check_spec_dir(d, static_only=True) if v["rule"] == "R1"]
            self.assertTrue([v for v in vs if "tasks-a.md" in v["message"]], vs)


class TestStatusAndReview(unittest.TestCase):
    def test_status_helper_reads_batches(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t, {"tasks-a.md": BATCH})
            text = aidd_status._read_tasks(d)
            self.assertIn("### T-03", text)
            self.assertIn("### T-01", text)

    def test_review_loads_batches_and_checks_size_per_file(self):
        big_a = BASE + "x" * 300_000
        big_b = BATCH + "y" * 300_000   # 600k together, each file under the 400k limit
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t, {"tasks-a.md": big_b}, base=big_a)
            sources = RV._load_sources(d)
            self.assertIn("### T-03", dict(sources)["tasks.md"])
            self.assertEqual(RV._oversize(sources), [])

    def test_review_refuses_one_oversized_batch_file_naming_it(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t, {"tasks-a.md": BATCH + "y" * 401_000})
            big = RV._oversize(RV._load_sources(d))
            self.assertEqual([n for n, _ in big], ["tasks-a.md"])

    def test_review_digest_changes_with_a_batch_edit(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t, {"tasks-a.md": BATCH})
            d1 = RV.sources_digest(d)
            (d / "tasks-a.md").write_text(BATCH + "\n- more\n", encoding="utf-8")
            self.assertNotEqual(d1, RV.sources_digest(d))

    def test_review_tag_without_batches_is_unchanged(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t)
            self.assertEqual(RV._approval_tag(d), "[tasks:" + BASE_HASH_PIN[:8] + "]")

    def test_review_tag_with_a_batch_covers_it(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t, {"tasks-a.md": BATCH})
            self.assertNotEqual(RV._approval_tag(d), "[tasks:" + BASE_HASH_PIN[:8] + "]")


class TestCheckSpec(unittest.TestCase):
    def test_check_spec_reads_task_blocks_of_batches(self):
        import check_spec
        with tempfile.TemporaryDirectory() as t:
            d = make_spec(t, {"tasks-a.md": BATCH})
            self.assertIn("### T-03", check_spec.read_tasks(d))


if __name__ == "__main__":
    unittest.main()
