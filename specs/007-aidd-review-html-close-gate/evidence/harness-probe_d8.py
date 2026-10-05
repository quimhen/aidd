import sys, unittest
sys.path.insert(0, r'D:\Fuentes\AIDD\tests')
import gate_fixtures as G
class P(G.Base):
    def test(self):
        R_ = str(self.root).replace(chr(92), '/')
        for sid in ('002-aidd-hard-rules', 'F23-eDoc-POS'):
            (self.root/'specs'/sid).mkdir(parents=True)
            for c in (f'echo x > {R_}/specs/{sid}/tasks.md', f'cp /tmp/t.md {R_}/specs/{sid}/plan.md',
                      f'echo x > specs/{sid}/tasks.md', f'cd specs/{sid} && echo x > spec.md',
                      f'echo "Approved: 2026-10-05 hash:abc" >> {R_}/specs/{sid}/tasks.md'):
                r = self.bash(c)
                print(sid, 'rc', r.returncode, '|', c)
unittest.main(argv=['x'], exit=False)
