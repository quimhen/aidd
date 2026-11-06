#!/usr/bin/env python3
"""
aidd_embed -- compress what AIDD embeds in its generated HTML pages (amendment 10 of spec 007, FR-409..FR-412).

One method for every page: UTF-8 text -> gzip (level 9, mtime 0, so the same input gives the same bytes) ->
base64 ASCII. The page decodes it with the browser's `DecompressionStream('gzip')` (Chrome/Edge 80+, Firefox 113+,
Safari 16.4+). Without that API the page shows a readable message instead of failing silently, and every
generator keeps a `--no-compress` switch that writes the plain JSON.

Measured 2026-11-05: docs/graphs/explorer.html 10.8 MB with the graph as plain JSON; gzip -9 = 626 KB (17x).

Stdlib only. Never prints. `pack`/`unpack` are exact inverses (byte-for-byte round trip, tested).
"""
import base64
import gzip

ENCODING = 'gzip+base64'

# Browser-side decoder, shared by the generators that embed it in their own <script>. Plain ES2018, no eval,
# no network. Returns the decoded text; rejects (never returns partial text) on any error.
JS_INFLATE = r"""
async function aiddInflate(b64) {
  if (typeof DecompressionStream === 'undefined') throw new Error('no-decompression-stream');
  var bin = atob(String(b64 || '').replace(/\s+/g, ''));
  var bytes = new Uint8Array(bin.length);
  for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  var stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
  return await new Response(stream).text();
}
"""


def pack(text):
    """base64(gzip-9(UTF-8 text)) as an ASCII str; deterministic (mtime 0)."""
    raw = text.encode('utf-8') if isinstance(text, str) else bytes(text)
    return base64.b64encode(gzip.compress(raw, compresslevel=9, mtime=0)).decode('ascii')


def unpack(b64):
    """Inverse of pack: the original text. Raises ValueError on a damaged payload."""
    try:
        return gzip.decompress(base64.b64decode(str(b64 or '').encode('ascii'), validate=False)).decode('utf-8')
    except Exception as exc:  # binascii.Error, OSError, EOFError, UnicodeDecodeError
        raise ValueError(f'embedded payload is not valid {ENCODING} ({type(exc).__name__})') from exc
