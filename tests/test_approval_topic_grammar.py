"""Bounded shared-topic regression; evidence and projects use temporary fixtures only."""
import os
import time
import unittest

import test_aidd_status as fixtures


class TestApprovalTopicGrammar(fixtures.Spec007Base):
    LABEL = "Aprobar con resumen"

    def attempt(self, root, d, expected_source=None):
        before = (d / "tasks.md").read_bytes()
        rc, out = self.inproc(fixtures.aidd_status.cmd_approve, str(d))
        if expected_source is None:
            self.assertEqual(rc, 1, out)
            self.assertEqual((d / "tasks.md").read_bytes(), before)
            self.assertEqual(fixtures.ev.events(root, kind="approved"), [], out)
        else:
            self.assertEqual(rc, 0, out)
            event = fixtures.ev.latest_approved(root, d.name)
            self.assertEqual(event["source"], expected_source)
        return out

    def test_summary_accepts_apruebas_and_existing_stems(self):
        for verb in ("Apruebas", "Aprobar", "Approve"):
            with self.subTest(verb=verb):
                tmp, root, d = self.project()
                with tmp:
                    self.answer(root, self.aq(d, f"¿{verb} estas tareas?"), self.LABEL)
                    self.attempt(root, d, "summary")

    def test_summary_preserves_tag_label_and_topic_refusals(self):
        cases = (
            ("¿Apruebas? [tasks:deadbeef]", self.LABEL),
            ("¿Apruebas estas tareas?", self.LABEL),
            ("¿Apruebas? {tag}", "No"),
            ("¿Cómo seguimos? {tag}", self.LABEL),
            ("¿Apruebas? {tag}", "aprobar con resumen"),
            ("¿Apruebas? {tag}", "Aprobar con resumen."),
        )
        for question, label in cases:
            with self.subTest(question=question, label=label):
                tmp, root, d = self.project()
                with tmp:
                    self.answer(root, question.format(tag=self.tag(d)), label,
                                options=[self.LABEL, "No", label])
                    self.attempt(root, d)

    def test_newer_apruebas_decline_cancels_older_aprobar_summary(self):
        tmp, root, d = self.project()
        with tmp:
            self.answer(root, self.aq(d, "¿Aprobar las tareas?"), self.LABEL)
            self.answer(root, self.aq(d, "¿Apruebas las tareas?"), "No")
            self.attempt(root, d)

    def test_ordinary_and_review_callers_accept_apruebas(self):
        for review in (False, True):
            with self.subTest(review=review):
                tmp, root, d = self.project()
                with tmp:
                    if review:
                        self.page(d)
                        self.review(d)
                    self.answer(root, self.aq(d, "¿Apruebas las tareas?"), "Approve")
                    self.attempt(root, d, "review+answer" if review else "answer")

    def test_ordinary_and_review_callers_preserve_refusals(self):
        for review in (False, True):
            for question, label in (("¿Apruebas? [tasks:deadbeef]", "Approve"),
                                    ("¿Apruebas?", "Approve"),
                                    ("¿Apruebas? {tag}", "No"),
                                    ("¿Cómo seguimos? {tag}", "Approve")):
                with self.subTest(review=review, question=question, label=label):
                    tmp, root, d = self.project()
                    with tmp:
                        if review:
                            self.page(d)
                            self.review(d)
                        self.answer(root, question.format(tag=self.tag(d)), label,
                                    options=["Approve", "No"])
                        self.attempt(root, d)

    def test_review_missing_stale_or_newer_context_still_refuses(self):
        for mode in ("missing", "stale", "newer"):
            with self.subTest(mode=mode):
                tmp, root, d = self.project()
                with tmp:
                    self.page(d)
                    if mode != "missing":
                        md = self.review(d, digest="0" * 40 if mode == "stale" else None)
                    self.answer(root, self.aq(d, "¿Apruebas las tareas?"), "Approve")
                    if mode == "newer":
                        future = time.time() + 5
                        os.utime(md, (future, future))
                    out = self.attempt(root, d)
                    if mode == "newer":
                        self.assertIn(f"Last consent found for `{self.tag(d)}`: answer at ", out)
                        self.assertIn("older than review.md", out)

    def test_summary_cannot_approve_different_canonical_unit_context(self):
        tmp, root, d = self.project()
        with tmp:
            tag = "[unit:001-x/a01:0123456789abcdef]"
            self.answer(root, f"¿Apruebas las tareas? {self.tag(d)}", self.LABEL)
            match = fixtures.aidd_status._unit_summary_consent(
                root, "s1", f"Aprobar unidad? {tag}\nCanonical package", tag, 0.0)
            self.assertIsNone(match)
            self.answer(root, f"¿Apruebas la unidad? {tag}", self.LABEL)
            match = fixtures.aidd_status._unit_summary_consent(
                root, "s1", f"Aprobar unidad? {tag}\nCanonical package", tag, 0.0)
            self.assertIsNone(match)
            self.assertEqual(fixtures.ev.events(root, kind="unit_approved"), [])
            self.assertEqual(fixtures.ev.events(root, kind="approved"), [])


if __name__ == "__main__":
    unittest.main()
