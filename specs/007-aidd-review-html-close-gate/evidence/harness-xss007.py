import sys, re, json, hashlib, base64, tempfile
from pathlib import Path
REPO = Path(r'D:\Fuentes\AIDD')
sys.path.insert(0, str(REPO/'skill'/'scripts')); sys.path.insert(0, str(REPO/'tests'))
import gate_fixtures as G
import aidd_review as RV
out=[]
td = Path(tempfile.mkdtemp())/'specs'/'F23-eDoc-POS'; td.mkdir(parents=True)
payload = '\n'.join([
 '## Heading with " quote and --> end', '<script>alert(1)</script>', '[x](javascript:alert(1))',
 '[x](java\tscript:alert(1))', '[x](\x01javascript:alert(1))', '[x](JaVaScRiPt:alert(1))', '[x](&#106;avascript:alert(1))',
 '[x](/\\evil.example/)', '[x](\\\\host\\share\\a.png)', '[x](//evil.example/a)', '![x](data:text/html,x)',
 '![x](https://evil.example/a.png)', '[x](../../x)', '[x](%2e%2e/x)', '[ok](https://example.com/p)', '```', '</script><script>alert(2)</script>', '```',
 '[a](https://x.y/"onmouseover="alert(1))', '![a" onerror="alert(1)](img.png)', '[`<b>`](https://e.x)',
 '[x](vbscript:msgbox)', '[x](https:evil)', '[x](  javascript:alert(1))', '| a | <img src=x onerror=alert(1)> |', '|---|---|', '| b | c |',
 '[x](%252e%252e/x)', '[x](javascript&colon;alert(1))', '[x](java%0ascript:alert(1))', '**[x](data:x)**', '*<svg/onload=alert(1)>*'])
(td/'spec.md').write_text(G.verified_spec()+'\n'+payload+'\n', encoding='utf-8')
(td/'tasks.md').write_text(G.tasks_text(), encoding='utf-8')
p, w = RV.generate(td)
h = p.read_text(encoding='utf-8')
scripts = re.findall(r'<script\b[^>]*>', h, re.I)
out.append(f'script tags: {scripts}')
js = re.search(r'<script id="aidd-js">(.*?)</script>', h, re.S).group(1)
sha = base64.b64encode(hashlib.sha256(js.encode('utf-8')).digest()).decode()
csp = re.search(r'Content-Security-Policy"\s+content="([^"]+)"', h)
out.append(f'CSP: {csp.group(1) if csp else None}')
out.append(f'CSP hash matches script: {("sha256-"+sha) in (csp.group(1) if csp else "")}')
hrefs = re.findall(r'\b(?:href|src)="([^"]*)"', h)
out.append(f'href/src values: {hrefs}')
bad = [x for x in hrefs if re.match(r'\s*(javascript|data|vbscript):', x, re.I) or x.startswith('//') or '..' in x]
out.append(f'bad href/src: {bad}')
body = re.sub(r'<script id="aidd-js">.*?</script>', '', h, flags=re.S)
out.append(f'on*= attrs in body: {re.findall(r"<[^>]*\son[a-z]+\s*=", body, re.I)[:5]}')
out.append(f'style= attrs: {re.findall(r"<[^>]*\sstyle\s*=", body, re.I)[:5]}')
data = re.search(r'<script type="application/json" id="aidd-data">(.*?)</script>', h, re.S).group(1)
json.loads(data); out.append('data blob parses; contains raw <: %s' % ('<' in data))
ext = [x for x in hrefs if x.startswith('http')]
out.append(f'external links: {ext}')
anchors = re.findall(r'<a [^>]*>', h)
out.append(f'anchors: {anchors}')
txt='\n'.join(out); print(txt)
(REPO/'specs'/'007-aidd-review-html-close-gate'/'evidence'/'xss-static.txt').write_text(txt+'\n', encoding='utf-8')
