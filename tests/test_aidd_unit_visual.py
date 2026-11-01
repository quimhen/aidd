import contextlib
import io
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import patch

from skill.scripts import aidd_unit_visual as visual
from skill.scripts import aidd_navigator as navigator


def test_visual_requires_explicit_origin_and_rechecks_package(tmp_path):
    spec = tmp_path / 'specs' / '001-test'
    spec.mkdir(parents=True)
    package = json.dumps({'unit': '001-test:change', 'version': '1', 'digest': 'a' * 64,
                          'parents': [], 'targets': [], 'tasks': [{'path': 'tasks.md', 'content': '<script>'}]})
    result, recorded = [], []
    output = io.StringIO()
    with patch.object(visual, '_unit', return_value=object()), \
            patch.object(visual.rules, 'unit_review_package', return_value=package) as make_package, \
            patch.object(visual.ev, 'append', side_effect=lambda *a, **kw: recorded.append(kw) or True), \
            contextlib.redirect_stdout(output):
        thread = threading.Thread(target=lambda: result.append(visual.serve_unit_review(spec, 'change', timeout=3)))
        thread.start()
        import time
        for _ in range(100):
            if output.getvalue().startswith('Revisión opcional'):
                break
            time.sleep(.01)
        url = output.getvalue().splitlines()[0].split(': ', 1)[1]
        origin = url.rsplit('/', 1)[0]
        token = url.rsplit('/', 1)[1]
        page = urllib.request.urlopen(url).read().decode()
        assert '&lt;script&gt;' in page
        assert '/navigator/' + token in page
        assert 'Centro de revisión' in urllib.request.urlopen(origin + '/navigator/' + token).read().decode()
        assert not recorded
        body = urllib.parse.urlencode({'token': token}).encode()
        request = urllib.request.Request(origin + '/approve', data=body)
        try:
            urllib.request.urlopen(request)
            assert False, 'a request without the browser origin was accepted'
        except urllib.error.HTTPError as exc:
            assert exc.code == 403
        make_package.return_value = package + 'changed'
        request.add_header('Origin', origin)
        try:
            urllib.request.urlopen(request)
            assert False, 'a stale package was accepted'
        except urllib.error.HTTPError as exc:
            assert exc.code == 409
        assert not recorded
        make_package.return_value = package
        assert urllib.request.urlopen(request).status == 200
        thread.join(5)
    assert result == [0]
    assert recorded[0]['digest'] == 'a' * 64
    assert recorded[0]['consent_source'] == 'local_visual'


def test_navigator_only_links_active_loopback_review_for_its_project(tmp_path):
    import os
    import time
    registry = tmp_path / 'aidd-unit-reviews'
    registry.mkdir()
    root = tmp_path / 'project'
    root.mkdir()
    item = {'project': os.path.normcase(str(root.resolve())), 'spec': '001-example',
            'unit': 'change', 'url': 'http://127.0.0.1:12345/' + 'a' * 40,
            'expires': time.time() + 30}
    (registry / 'review-good.json').write_text(json.dumps(item), encoding='utf-8')
    bad = dict(item, url='http://example.com/' + 'a' * 40)
    (registry / 'review-bad.json').write_text(json.dumps(bad), encoding='utf-8')
    with patch.object(navigator.tempfile, 'gettempdir', return_value=str(tmp_path)):
        assert navigator._active_unit_reviews(root) == {'001-example': [{'unit': 'change', 'url': item['url']}]}
        assert not navigator._active_unit_reviews(tmp_path)


def test_task_markdown_is_readable_and_escaped():
    result = visual._markdown('# Alcance\n\n| Tarea | Estado |\n| --- | --- |\n| <script> | Pendiente |\n\n- Revisar')
    assert '<h3>Alcance</h3>' in result
    assert '<th>Tarea</th>' in result and '<td>Pendiente</td>' in result
    assert '&lt;script&gt;' in result and '<script>' not in result
    assert '<li>Revisar</li>' in result
