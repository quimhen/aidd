"""Synthetic public-API consent records; no real owner evidence is modified."""
import ast
import time
from pathlib import Path
from unittest import mock
from test_aidd_status import Spec007Base, aidd_status, ev, tick


class TestNativeSummaryApproveCompat(Spec007Base):
    TAG = "[tasks:1234abcd]"
    SESSION = "s1"
    QUESTION = "¿Apruebas con resumen estas tareas [tasks:1234abcd]? No cambian producción. Elige «Approve» para aprobarlas."

    def _record_native_answer(self, root, question=None, answer="Approve", options=None,
                              session="s1", anchor=True, anchor_question=None,
                              anchor_options=None, tool_use_id="call_native_summary_fixture"):
        question = question or self.QUESTION
        options = options if options is not None else ["Approve", "Request changes"]
        if anchor:
            ev.append_question(root, session, anchor_question or question,
                               options=[anchor_options if anchor_options is not None else options],
                               tool_use_id=tool_use_id)
            tick()
        ev.append_answer(root, session, answer, [[question, answer]], options=[options], tool_use_id=tool_use_id)
        return ev.events(root, session=session, kind="answer")[-1]

    def _summary(self, root, session="s1", since=0):
        return aidd_status._summary_answer(ev, root, session, since, self.TAG)

    def _refused(self, **kwargs):
        tmp, root, _ = self.project()
        with tmp:
            self._record_native_answer(root, **kwargs)
            self.assertIsNone(self._summary(root))
            self.assertEqual(ev.events(root, kind="approved"), [])

    def test_native_explicit_summary_approve_accepts_original_event(self):
        tmp, root, _ = self.project()
        with tmp:
            original = self._record_native_answer(root)
            self.assertEqual(self._summary(root), original)
            self.assertEqual(ev.events(root, kind="answer")[-1]["detail"]["pairs"], [[self.QUESTION, "Approve"]])
            self.assertEqual(ev.events(root, kind="approved"), [])

    def test_legacy_spanish_summary_route_unchanged(self):
        for session in (self.SESSION, "unknown-session"):
            with self.subTest(session=session):
                tmp, root, _ = self.project()
                with tmp:
                    row = self._record_native_answer(root, question=f"¿Aprobar tareas {self.TAG}?",
                                                     answer="Aprobar con resumen", options=["Aprobar con resumen", "Other"], session=session)
                    self.assertEqual(self._summary(root), row)

    def test_plain_approve_without_summary_intent_refused(self):
        self._refused(question=f"¿Aprobar tareas {self.TAG}?")

    def test_negated_quoted_conditional_or_alternative_intent_refused(self):
        questions = [f"¿No apruebas con resumen {self.TAG}?", f'"¿Apruebas con resumen {self.TAG}?"',
                     self.QUESTION + " No apruebes este resumen."]
        suffixes = ("si pasa X", "cuando se autorice X", "siempre que pase X", "en caso de X",
                    "sujeto a X", "condicionado a X", "a condición de X", "hasta que pase X",
                    "o en HTML", "u otra modalidad", "versus HTML", "vs HTML", "sin aprobar")
        questions += [f"¿Apruebas con resumen {self.TAG} {suffix}?" for suffix in suffixes]
        for question in questions:
            with self.subTest(question=question):
                self._refused(question=question)

    def test_nonoffered_or_mismatched_question_anchor_refused(self):
        cases = ({"options": ["Request changes"]}, {"anchor": False}, {"tool_use_id": None},
                 {"anchor_question": f"¿Aprobar tareas {self.TAG}?"}, {"anchor_options": ["Approve", "Other"]})
        for case in cases:
            with self.subTest(case=case):
                self._refused(**case)

    def test_wrong_or_missing_task_tag_refused(self):
        for question in (self.QUESTION.replace(self.TAG, "[tasks:feedface]"), self.QUESTION.replace(self.TAG, ""),
                         f"¿Apruebas con resumen estas tareas? {self.TAG}"):
            with self.subTest(question=question):
                self._refused(question=question)

    def test_stale_or_future_answer_refused(self):
        tmp, root, _ = self.project()
        with tmp:
            row = self._record_native_answer(root)
            self.assertIsNone(self._summary(root, since=row["ts"] + 1))
            with mock.patch.object(aidd_status.time, "time", return_value=row["ts"] - 10):
                self.assertIsNone(self._summary(root))

    def test_wrong_or_unknown_session_refused(self):
        for session in ("s2", "unknown-session"):
            with self.subTest(session=session):
                self._refused(session=session)
        tmp, root, _ = self.project()
        with tmp:
            self._record_native_answer(root, session="unknown-session")
            self.assertIsNone(self._summary(root, session="unknown-session"))

    def test_typed_or_forged_raw_answer_refused(self):
        for kind in ("prompt", "answer"):
            with self.subTest(kind=kind):
                tmp, root, _ = self.project()
                with tmp:
                    ev.append(root, self.SESSION, kind, text=self.QUESTION + " Approve")
                    self.assertIsNone(self._summary(root))
                    self.assertEqual(ev.events(root, kind="approved"), [])

    def test_newer_rejection_or_invalid_intent_cancels_older_consent(self):
        for old in ("Approve", "Aprobar con resumen"):
            for newer in ("reject", "plain", "not-offered"):
                with self.subTest(old=old, newer=newer):
                    tmp, root, _ = self.project()
                    with tmp:
                        self._record_native_answer(root, answer=old, options=[old, "Request changes"], tool_use_id="call_old")
                        tick()
                        kwargs = {"answer": "Request changes"} if newer == "reject" else (
                            {"question": f"¿Aprobar tareas {self.TAG}?"} if newer == "plain" else {"options": ["Request changes"]})
                        self._record_native_answer(root, tool_use_id="call_new", **kwargs)
                        self.assertIsNone(self._summary(root))

    def test_nonoffered_spanish_pair_cannot_trampoline_through_english_pair(self):
        for session, english in ((self.SESSION, f"¿Aprobar tareas {self.TAG}?"),
                                 ("unknown-session", self.QUESTION)):
            with self.subTest(session=session, english=english):
                tmp, root, _ = self.project()
                with tmp:
                    spanish = f"¿Aprobar tareas {self.TAG}?"
                    options = [["Request changes"], ["Approve", "Request changes"]]
                    ev.append_question(root, session, spanish + "\n" + english,
                                       options=options, tool_use_id="call_mixed_native")
                    tick()
                    ev.append_answer(root, session, "Mixed native answer fixture",
                                     [[spanish, "Aprobar con resumen"], [english, "Approve"]],
                                     options=options, tool_use_id="call_mixed_native")
                    self.assertIsNone(self._summary(root))
                    self.assertEqual(ev.events(root, kind="approved"), [])

    def test_adapter_mirror_matches_canonical_summary_implementation(self):
        base = Path(__file__).resolve().parents[1]
        def functions(path):
            tree = ast.parse(path.read_text(encoding="utf8"))
            return {node.name: ast.dump(node, include_attributes=False) for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name in
                    ("_summary_answer", "_native_summary_approve_question")}
        self.assertEqual(functions(base / "skill/scripts/aidd_status.py"),
                         functions(base / "adapters/dot-aidd/scripts/aidd_status.py"))
