"""Tests for skill/scripts/flowmap.py (AIDD Flowmap) — stdlib unittest."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import flowmap  # noqa: E402

GOOD = """flow: US-001
title: Open a table
status: draft
actors[2]{id,label,kind}:
  w,Waiter,human
  pos,POS,system
processes[1]{id,label}:
  P1,Choose
steps[6]{id,actor,process,type,code,label,detail}:
  s1,w,P1,start,,Enter,
  s2,pos,P1,screen,SCREEN-01,Table map,
  s3,pos,P1,decision,CTL-004,Open?,"checks API-012, then ticket"
  s4,pos,P1,error,,Busy,
  s5,pos,P1,screen,SCREEN-08,Order,
  s6,w,P1,end,,Done,
links[6]{from,to,label,role}:
  s1,s2,,main
  s2,s3,,main
  s3,s4,busy,error
  s3,s5,free,main
  s5,s6,,main
  s4,s2,retry,return
"""


def run(text):
    flows, perr = flowmap.parse_toon(text)
    return flows, flowmap.validate(flows, perr)


class TestFlowmap(unittest.TestCase):
    def test_good_flow_validates(self):
        flows, (errors, _) = run(GOOD)
        self.assertEqual(errors, [])
        self.assertEqual(flows[0]["nodes"][2]["detail"], "checks API-012, then ticket")

    def test_row_count_mismatch(self):
        _, (errors, _) = run(GOOD.replace("steps[6]", "steps[7]"))
        self.assertTrue(any("declares 7 rows" in e for e in errors))

    def test_dangling_link_and_dead_end(self):
        _, (errors, _) = run(GOOD.replace("s5,s6,,main", "s5,s9,,main"))
        self.assertTrue(any("unknown step" in e for e in errors))

    def test_decision_branch_needs_label(self):
        _, (errors, _) = run(GOOD.replace("s3,s5,free,main", "s3,s5,,main"))
        self.assertTrue(any("no condition label" in e for e in errors))

    def test_screen_requires_code_and_prefix(self):
        _, (errors, _) = run(GOOD.replace("s2,pos,P1,screen,SCREEN-01", "s2,pos,P1,screen,"))
        self.assertTrue(any("must cite its code" in e for e in errors))
        _, (errors, _) = run(GOOD.replace("screen,SCREEN-01", "screen,CTL-001"))
        self.assertTrue(any("cannot cite" in e for e in errors))

    def test_unreachable_step(self):
        text = GOOD.replace("steps[6]", "steps[7]").replace("  s6,w,P1,end,,Done,", "  s6,w,P1,end,,Done,\n  s7,w,P1,end,,Island,")
        _, (errors, _) = run(text)
        self.assertTrue(any("s7" in e for e in errors))

    def test_pseudocode_has_branches_and_goto(self):
        flows, _ = run(GOOD)
        text = "\n".join(t for _, _, t in flowmap.pseudocode(flows[0]))
        self.assertIn("IF busy:", text)
        self.assertIn("ELSE (free):", text)
        self.assertIn("GOTO s2", text)

    def test_html_is_self_contained_and_interactive(self):
        flows, _ = run(GOOD)
        page = flowmap.render_html(flows)
        self.assertIn("<svg", page)
        self.assertIn('data-id="s3"', page)
        self.assertNotIn("http://", page.replace("http://www.w3.org/2000/svg", ""))

    def test_cli_check_and_render(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "visual-flow.toon"
            src.write_text(GOOD, encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPTS / "flowmap.py"), str(src), "--check"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout)
            r = subprocess.run([sys.executable, str(SCRIPTS / "flowmap.py"), str(src)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertTrue((Path(d) / "visual-flow.html").exists())

    def test_template_is_valid(self):
        tpl = SCRIPTS.parent / "templates" / "visual-flow.toon"
        _, errors, _ = flowmap.check_file(tpl)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
