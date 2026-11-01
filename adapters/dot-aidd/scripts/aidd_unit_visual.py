"""Optional local, human-operated approval for one versioned unit.

The loopback server is a local-user trust boundary, not authentication against
other processes running as the same user. It must never be operated by an agent
on the owner's behalf. Loading the page alone does not record consent.
"""
import hashlib
import html
import json
import os
import re
import secrets
import tempfile
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

try:
    from . import aidd_evidence as ev, aidd_rules as rules
    from .aidd_units import discover_unit_scope
except ImportError:
    import aidd_evidence as ev
    import aidd_rules as rules
    from aidd_units import discover_unit_scope


def _unit(root, spec, unit_id):
    matches = [u for u in discover_unit_scope(root, spec, [spec + ':' + unit_id])
               if u.spec_id == spec and u.unit_id == unit_id]
    if len(matches) != 1:
        raise ValueError('unit not found or ambiguous')
    return matches[0]


def _inline(text):
    escaped = html.escape(text)
    escaped = re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)
    return re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', escaped)


def _markdown(text):
    """Render a conservative subset of task Markdown; escape all content."""
    lines = text.splitlines()
    output = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith('```'):
            i += 1
            block = []
            while i < len(lines) and not lines[i].strip().startswith('```'):
                block.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            output.append('<pre>' + html.escape('\n'.join(block)) + '</pre>')
            continue
        if line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            if level <= 6 and line[level:level + 1] == ' ':
                tag = min(level + 2, 6)
                output.append(f'<h{tag}>' + _inline(line[level:].strip()) + f'</h{tag}>')
                i += 1
                continue
        def cells(row):
            return [c.strip() for c in row.strip().strip('|').split('|')]
        if (line.startswith('|') and i + 1 < len(lines) and
                re.fullmatch(r'[| :\-]+', lines[i + 1].strip())):
            header = ''.join('<th>' + _inline(c) + '</th>' for c in cells(line))
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                rows.append('<tr>' + ''.join('<td>' + _inline(c) + '</td>' for c in cells(lines[i])) + '</tr>')
                i += 1
            output.append('<div class="table-wrap"><table><thead><tr>' + header +
                          '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>')
            continue
        if line.startswith(('- ', '* ')):
            entries = []
            while i < len(lines) and lines[i].strip().startswith(('- ', '* ')):
                entries.append('<li>' + _inline(lines[i].strip()[2:]) + '</li>')
                i += 1
            output.append('<ul>' + ''.join(entries) + '</ul>')
            continue
        output.append('<p>' + _inline(line) + '</p>')
        i += 1
    return ''.join(output)


def _page(package, token):
    data = json.loads(package)
    esc = html.escape
    sections = ''.join('<section><h2>' + esc(t['path']) + '</h2>' +
                       _markdown(t['content']) + '</section>' for t in data['tasks'])
    metadata = ''.join('<dt>' + esc(label) + '</dt><dd>' + esc(', '.join(data.get(key, [])) or 'Ninguno') + '</dd>'
                       for label, key in [('Dependencias', 'parents'), ('Archivos afectados', 'targets'),
                                          ('Entradas', 'inputs'), ('Configuración', 'config')])
    visual_refs = '<section><h2>Referencias visuales</h2><pre>' + esc(
        json.dumps(data.get('visual_refs', []), ensure_ascii=False, indent=2)) + '</pre></section>'
    return ('<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1"><title>Revisión de unidad · AIDD</title>'
            '<style>body{margin:0;background:#edf3f4;color:#182d3c;font:16px Segoe UI,Arial,sans-serif}'
            'header{background:#122b3a;color:white;padding:18px 5%}main{max-width:1100px;margin:30px auto;padding:0 20px}'
            'section,.card{background:white;border:1px solid #d8e3e7;border-radius:9px;padding:20px;margin:16px 0}'
            'h1{font-size:28px}h2{font-size:16px;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
            'dt{font-weight:bold}dd{margin:4px 0 14px;overflow-wrap:anywhere}button{background:#17657a;color:white;'
            'border:0;border-radius:6px;padding:12px 18px;font-weight:bold;cursor:pointer}small{overflow-wrap:anywhere}'
            '.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%}th,td{text-align:left;border:1px solid #d8e3e7;padding:10px}th{background:#f4f8f9}a{color:#17657a}'
            '</style><header>AIDD · Centro de revisión</header><main><h1>Revisar esta versión</h1>'
            '<p><a href="/navigator/' + esc(token, quote=True) + '">Abrir visor completo: árbol, plan e historial</a></p>'
            '<div class="card"><p>Unidad: <strong>' + esc(data['unit']) + '</strong> · Versión: ' +
            esc(data.get('version', '1')) + '</p><dl>' + metadata + '</dl><small>Huella SHA-256: ' +
            esc(data['digest']) + '</small></div>' + visual_refs + sections +
            '<div class="card"><p>Al aprobar, autorizas únicamente esta unidad y el contenido mostrado. '
            'Abrir esta página no constituye aprobación.</p><form method="post" action="/approve">'
            '<input type="hidden" name="token" value="' + esc(token, quote=True) + '">'
            '<button type="submit">Aprobar esta versión</button></form></div></main></html>').encode('utf-8')


def serve_unit_review(spec_dir, unit_id, *, open_browser=False, timeout=3600):
    """Show an exact package and record only a matching, explicit local POST."""
    spec_dir = Path(spec_dir).resolve(strict=True)
    if spec_dir.parent.name != 'specs':
        raise ValueError('unit review requires a spec under project specs/')
    root = spec_dir.parent.parent
    unit = _unit(root, spec_dir.name, unit_id)
    package = rules.unit_review_package(unit, root)
    data = json.loads(package)
    token = secrets.token_urlsafe(32)
    state = {'approved': False, 'seen': False}
    page = _page(package, token)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, code, body, *, navigator=False):
            self.send_response(code)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Content-Type-Options', 'nosniff')
            policy = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"
            if navigator:
                policy += "; script-src 'unsafe-inline'; img-src data:"
            self.send_header('Content-Security-Policy', policy)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/navigator/' + token:
                try:
                    try:
                        from .aidd_navigator import build_navigator
                    except ImportError:
                        from aidd_navigator import build_navigator
                    return self.respond(200, build_navigator(root).encode('utf-8'), navigator=True)
                except (OSError, ValueError):
                    return self.respond(500, b'Navigator unavailable')
            if self.path != '/' + token:
                return self.respond(404, b'Not found')
            state['seen'] = True
            self.respond(200, page)

        def do_POST(self):
            origin = 'http://127.0.0.1:' + str(self.server.server_port)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    return self.respond(400, b'Invalid request length')
                body = self.rfile.read(length)
            except (OSError, ValueError):
                return self.respond(400, b'Invalid request')
            if (self.path != '/approve' or not state['seen'] or state['approved'] or
                    self.headers.get('Origin') != origin or
                    self.headers.get('Content-Type', '').split(';')[0] != 'application/x-www-form-urlencoded'):
                return self.respond(403, b'Refused')
            try:
                fields = parse_qs(body.decode('ascii'), strict_parsing=True)
                if set(fields) != {'token'} or len(fields['token']) != 1 or not secrets.compare_digest(fields['token'][0], token):
                    raise ValueError('invalid token')
                current = _unit(root, spec_dir.name, unit_id)
                if rules.unit_review_package(current, root) != package:
                    return self.respond(409, 'La unidad cambió. Vuelve a abrir la revisión.'.encode('utf-8'))
                if not ev.append(root, 'local-visual', 'unit_approved', spec=spec_dir.name,
                                 unit_id=unit_id, digest=data['digest'], consent_ts=time.time(),
                                 review_sha256=hashlib.sha256(package.encode('utf-8')).hexdigest(),
                                 consent_source='local_visual'):
                    raise ValueError('could not record approval')
                state['approved'] = True
                self.respond(200, 'Aprobación registrada para esta versión. Puedes cerrar esta página.'.encode('utf-8'))
            except (OSError, ValueError, UnicodeError):
                self.respond(400, 'No se registró la aprobación.'.encode('utf-8'))

    with HTTPServer(('127.0.0.1', 0), Handler) as server:
        server.timeout = min(1.0, max(0.01, timeout))
        url = f'http://127.0.0.1:{server.server_port}/{token}'
        print('Revisión opcional de la unidad: ' + url, flush=True)
        print('Solo el usuario debe pulsar Aprobar esta versión.', flush=True)
        registry = Path(tempfile.gettempdir()) / 'aidd-unit-reviews'
        registry.mkdir(mode=0o700, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='review-', suffix='.json', dir=registry)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump({'project': os.path.normcase(str(root.resolve())), 'spec': spec_dir.name,
                           'unit': unit_id, 'url': url, 'expires': time.time() + timeout}, stream)
            if open_browser:
                webbrowser.open(url)
            deadline = time.monotonic() + timeout
            while not state['approved'] and time.monotonic() < deadline:
                server.handle_request()
        finally:
            Path(name).unlink(missing_ok=True)
    return 0 if state['approved'] else 2
