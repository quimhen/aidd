import json
import os
import tempfile
import time
from pathlib import Path
from unittest import TestCase

from skill.scripts import aidd_evidence as ev
from skill.scripts import aidd_rules as rules
from skill.scripts import aidd_status as st


class TestPerfAndCache(TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        (self.root / 'specs').mkdir(parents=True)
        (self.root / '.aidd' / 'evidence').mkdir(parents=True)
        self.old_env = {k: os.environ.get(k) for k in ('AIDD_EVIDENCE_DIR', 'AIDD_TESTING')}
        os.environ['AIDD_EVIDENCE_DIR'] = str(self.root / '.aidd' / 'evidence')
        os.environ['AIDD_TESTING'] = '1'

    def tearDown(self):
        for k, v in self.old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.td.cleanup()

    def test_last_code_edit_ts_ignores_docs_and_aidd(self):
        # A doc edit or .aidd write does not count as a code edit
        ev.append(self.root, 'sess', 'code_edit', path=str(self.root / 'README.md'))
        ev.append(self.root, 'sess', 'code_edit', path=str(self.root / '.aidd' / 'status-cache.json'))
        ev.append(self.root, 'sess', 'code_edit', path=str(self.root / 'specs' / '001' / 'spec.md'))
        self.assertEqual(ev.last_code_edit_ts(self.root), 0.0)

        # Real code edit does count
        ev.append(self.root, 'sess', 'code_edit', path=str(self.root / 'src' / 'main.py'))
        self.assertGreater(ev.last_code_edit_ts(self.root), 0.0)

    def test_closed_spec_status_cache(self):
        spec_dir = self.root / 'specs' / '001-demo'
        spec_dir.mkdir(parents=True)
        (spec_dir / 'spec.md').write_text('# Demo\n\n## Pipeline route\n| Artifact | Path |\n', encoding='utf-8')
        (spec_dir / 'tasks.md').write_text('## Waves\n| Wave | Tasks | Agent time (min) | Human ref (h) | Tokens (k) |\n| 1 | T-01 | 5 | 1 | 10 |\n\n### T-01\nAgent min: 5\nHuman ref hours: 1\nTokens (est): 10k\nAgent role: builder\nModel tier: standard\n\nApproved: 2026-10-01 hash:deadbeef1234\n', encoding='utf-8')
        
        # Close the spec
        ev.append_spec_closed(self.root, 'sess', '001-demo', 'completed', 'deadbeef1234')

        # First status call: computes and caches
        s1 = st.build_status(spec_dir, root=self.root)
        self.assertEqual(s1['spec'], '001-demo')
        self.assertFalse(s1['open'])

        # Check in-memory cache hit
        ck = (str(spec_dir), st._spec_signature(spec_dir), st._events_sig(self.root), st._git_head_sig(self.root))
        self.assertIn(ck, st._STATUS_MEM_CACHE)

        # Second status call: returns cached instance with dynamic fields
        s2 = st.build_status(spec_dir, root=self.root)
        self.assertEqual(s2['spec'], '001-demo')

        # Mutating spec.md invalidates the cache
        time.sleep(0.01)
        (spec_dir / 'spec.md').write_text('# Demo Updated\n', encoding='utf-8')
        ck_new = (str(spec_dir), st._spec_signature(spec_dir), st._events_sig(self.root), st._git_head_sig(self.root))
        self.assertNotEqual(ck, ck_new)
        s3 = st.build_status(spec_dir, root=self.root)
        self.assertEqual(s3['spec'], '001-demo')

    def test_open_debt_blocking_memoization(self):
        spec_dir = self.root / 'specs' / '002-debt'
        spec_dir.mkdir(parents=True)
        (spec_dir / 'spec.md').write_text('# Debt\n\n## Visual debt\n| Screen | Blocks spec | Reason |\n', encoding='utf-8')
        
        # Call open_debt_blocking multiple times
        d1 = rules.open_debt_blocking(self.root)
        d2 = rules.open_debt_blocking(self.root)
        self.assertEqual(d1, d2)
