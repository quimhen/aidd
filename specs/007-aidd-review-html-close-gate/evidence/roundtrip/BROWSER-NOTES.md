# T-11 browser evidence (Chrome via claude-in-chrome, page served from http://127.0.0.1:8765)

BLOCKER: file:// is refused by both browser tools (claude-in-chrome: "Can't interact with browser-internal or
unparseable URLs"; Docker playwright: 'Access to "file:" protocol is blocked'). Everything below was therefore
done over http://127.0.0.1 (same-origin). Still UNVERIFIED: a relative image under the CSP from a real file:// origin
(img-src 'self'). Recommend img-src 'self' file: data: if the owner sees broken images from file://; test by hand.

Verified in a real browser (review.html, 121 sections, F13-shaped):
- Renders; no console errors; sticky header; checkboxes + textareas injected; progress "0 / 121 approved".
- "Approve all" -> 120/121; the one data-mandatory section (spec/verification) stayed unchecked; checking it by
  hand -> 121/121.
- Comment typed in section 1; Send -> blob text is the expected grammar (front matter, `## key`, `- [x] Approved`,
  `> ` prefixed comment lines, approved: true). Banner with consent line shown.
- 390 px (iframe 390 wide; window resize tool did not give a real 390 viewport): scrollWidth == clientWidth (371),
  no horizontal page scroll; tables scroll inside their own box.
- XSS fixture (AC-204 spec + window.__pwned marker script/onerror): no script ran (__pwned undefined), 2 script
  elements only (aidd-data, aidd-js), 0 style attrs, 0 on* handlers, only the https://ok.example link kept,
  no securitypolicyviolation, no network request left the page, no console messages.
- Relative image shot.png: an eager `new Image()` for it loads under the CSP (img-src 'self') over http.
  The in-page <img loading="lazy"> stayed incomplete in this automation tab (not visible in the shrunk viewport);
  not conclusive.

Defects / notes for the main agent:
1. <title> and the h1 read "Review Review F13-..." (TITLE already contains "Review"): cosmetic duplication.
2. The first section heading shows "spec.md" file label above; the sticky header title is scrolled/hidden by the
   warning box in the desktop screenshot (a yellow warning box overlaps the sticky header bottom edge) - minor.
3. Lazy image not confirmed (see above).
