# Draft — amendment 06 to spec 007: the alias graph is a registered graph and the explorer can draw it

**DRAFT: not approved, not executable, no `Approved:` line.** Amendment intake: `AMENDMENT` of
`specs/007-aidd-review-html-close-gate`. Follow-up of amendment 04 (which reads `.aidd/graphs/path-aliases.toon` only inside
`aidd_progress`). Owner direction (verbatim, 2026-11-03): "si adicionamos un grafo en aidd este tambien se debe poder leer con el explorer" and
"si redacta la enmienda y luego le das la instruccion a agy para que haga el cambio y utilice el mcp stitch para la parte grafica del html".

**Sequencing rule (R4, do not skip).** The visual source of truth for `SCREEN-901` is a Stitch mockup that does not exist yet. Phase 1 (agy, no code):
generate it with the Stitch MCP and save a local snapshot with its SHA-256 under `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/`. The owner approves
the mockup. Only then this amendment is merged into spec 007 (the mockup path is its `Mockup source`, so no open visual-debt row blocks the spec)
and its tasks are approved. Phase 2 (agy): implement T-35..T-41.

**Re-based 2026-11-03 on `specs/004-aidd-graph-first/amendment-unified-explorer.draft.md` (the 004 amendment).** That amendment
ports the F47 explorer into AIDD, makes every registered graph a layer (pill, checkbox, colour generated from the registry
name), and adopts ALL the controls of this mockup for every layer (zoom in, out, reset, zoom level, fit, centre, copy node,
theme toggle), on owner decision "Sí, adoptar todos los controles". Consequences here: the former T-42 (adopt the F47
explorer) is removed, superseded by its T-74..T-76; T-38 keeps only the alias-specific view; no control task exists in this
amendment. Phase 2 starts after wave 10 of the 004 amendment.

## Minimum Requirements Checklist

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | `skill/scripts/aidd_graphs.py`, `graph_explorer.py`, `aidd_progress.py`, new `alias_graph.py` | repo — `skill/scripts/aidd_graphs.py:176` | — |
| New development or modification? | One new module and three modifications; mirrors by `cp` | repo — `skill/scripts/aidd_graphs.py:889` | — |
| External service, API, integration? | Stitch MCP for the design only (no runtime dependency); the explorer stays single-file with zero CDN | user — "utilice el mcp stitch para la parte grafica del html" | — |
| Who is requesting it? | Owner | user — "si adicionamos un grafo en aidd este tambien se debe poder leer con el explorer" | — |
| Dependencies? | Amendment 04 (`path-aliases.toon` format, `renamed` state); the 004 amendment (unified explorer, `unified_graph.TOON_READERS`, adopted controls) | repo — `specs/007-aidd-review-html-close-gate/amendment-04-task-state-resolution.draft.md`, `specs/004-aidd-graph-first/amendment-unified-explorer.draft.md` | — |
| Business objective | A reviewer sees which files were renamed or deleted and which tasks they resolve, in the same explorer as the other graphs | user — "tambien se debe poder leer con el explorer" | — |
| Expected visual fidelity | exact: replicate the approved Stitch mockup (structure, legend, states, spacing); no functional-only shortcut | `[Proposed — unconfirmed]` (owner to confirm when approving the mockup) | owner |

## Executive summary

- **Objective:** register the alias graph as a built-in graph kind `aliases`, query it with `aidd graphs show aliases <name>`, draw it with
  `aidd graphs explorer aliases`, and show task states `renamed` and delete-only in the `progress` graph.
- **Today (verified 2026-11-03):** `aidd graphs list/status/show` know only graphs declared in `aidd_graphs.py` or in the charter `## Graphs` table; a loose
  `.toon` is invisible. `aidd graphs explorer` hands the graph `output` unchanged to `graph_explorer.py`.
- **Two different explorers exist (verified 2026-11-03).** The AIDD source `skill/scripts/graph_explorer.py` is a 207-line searchable LIST viewer (ids `q`, `list`, `card`; no canvas, legend or details panel).
  b1SycLink's `.aidd/scripts/graph_explorer.py` (F47, "Executive Precision Unified Graph Explorer", 1371 lines) is an interactive Canvas 2D viewer with an omnibox search
  (`omnibox-input`), an `inspector-drawer` details panel, per-layer checkboxes and metric pills; it accepts the same `--graph <graph.json>` plus `--root`, and never returned to the AIDD source.
  The approved SCREEN-901 mockup (canvas, details panel, legend, search) matches the second one, not the first.
- **Design choice (re-based):** (1) the 004 amendment adopts the F47 explorer, generates one layer per registered graph and adds the mockup's 8 controls for every layer; (2) here, T-36 writes the alias reader, T-37 registers the graph, and T-38 registers `TOON_READERS["aliases"]` in `unified_graph.py` and adds ONLY the alias-specific view of the layer `aliases` (legend with the three states, `RENAMED_TO` edge style, inspector rows scope and reason, empty banner, task `state` colours). The pill `metric-aliases`, the checkbox `layer-cb-aliases` and the colour `--layer-aliases` come from the registry name, not from this amendment. The mockup is the visual source of the alias view, not a separate page.
- **Not in scope:** generating the alias file (a project script does that, for b1SycLink from `rename_map.csv`); the explorer base and its controls (004 amendment).
- **Risk:** the visual part is the only subjective part; it is pinned to an approved mockup and measured by tests on DOM/legend/state attributes, not by eye.

## Functional requirements

| Code | Requirement | Source |
|---|---|---|
| FR-250 | `aidd_graphs.py` `_builtin_registry` (the function that builds the list returned at line 181) adds `{"name": "aliases", "kind": "aliases", "output": ".aidd/graphs/path-aliases.toon", "refresh": "", "watch": [".aidd/graphs/path-aliases.toon"]}` only when that file exists AND no graph named `aliases` is already declared by the charter `## Graphs` table (a project such as b1SycLink declares it there with its own generator `python tools/gen_path_aliases.py --out .aidd/graphs/path-aliases.toon`; the charter row wins and no duplicate or `-renamed` entry is produced). `refresh` stays empty in the built-in row: the project generates the file, AIDD never builds it. | repo — `skill/scripts/aidd_graphs.py:167-181` |
| FR-251 | `show(root, "aliases", query, limit=25)` returns, in at most `limit` lines, the rows whose old or new base name contains `query` (case-insensitive), as `old -> new [scope] reason`; no match returns `No alias matching '<query>'.`; a missing or unreadable file returns the message `Graph 'aliases' is missing; the project must generate .aidd/graphs/path-aliases.toon`. Never raises. | repo — `skill/scripts/aidd_graphs.py:889-907` |
| FR-252 | New module `skill/scripts/alias_graph.py` is the ONLY reader of the format: `parse_aliases(text)`, `load_aliases(path)`, `to_graph(rows)`, `show_aliases(root, query, limit=25)`. Fail closed: any error gives `[]`/an empty graph, never an exception. | amendment 04 FR-233 |
| FR-253 | `unified_graph.TOON_READERS` gains `"aliases"`, a reader that returns `alias_graph.to_graph(alias_graph.parse_aliases(text))`; so `graph_explorer.py --graph x.toon --kind aliases --layer aliases` and the unified explorer (`aidd graphs explorer`) both draw the alias graph. JSON input is untouched (owned by the 004 amendment). | 004 amendment FR-061 |
| FR-254 | `to_graph(rows)` returns `{"nodes": [...], "edges": [...]}` with node `{"id": "old:<base>"|"new:<base>", "label": <base>, "type": "alias_old"|"alias_new", "scope", "reason"}` and edge `{"source": <old id>, "target": <new id>, "type": "RENAMED_TO"}`; a base name that is both an old and a new name keeps both nodes; duplicate rows collapse to one edge. | owner brief 2026-11-03 |
| FR-255 | The alias-specific view of the layer `aliases` (SCREEN-901) replicates the approved Stitch mockup: legend with the three node states (`old name`, `new name`, `renamed in progress`), the `RENAMED_TO` edge style and badge, the inspector rows scope and reason, the empty banner; colours from the mockup's state tokens (old, new, progress) in dark and light. Layer pill, checkbox and colour come from the registry; the controls come from the 004 amendment. Zero external requests: all CSS, JS and data inline. | user — "utilice el mcp stitch para la parte grafica del html" |
| FR-256 | `aidd_progress.py` graph writer adds to each task node the attribute `state` with the value `renamed` or `deleted` when `task_state` resolved it that way, and the explorer colours task nodes by that attribute. Nodes without the attribute are unchanged. | amendment 04 FR-234 |
| FR-257 | `aidd_progress._load_aliases` (amendment 04) delegates to `alias_graph.load_aliases` so the format has a single reader; every amendment-04 test stays green. | Shared-First rule (SKILL.md) |
| FR-258 | SUPERSEDED (2026-11-03) by FR-067 of the 004 amendment (`specs/004-aidd-graph-first/amendment-unified-explorer.draft.md`); kept only as a pointer, no task here. | 004 amendment |

## Acceptance criteria

| Code | Scenario | Expected |
|---|---|---|
| AC-291 | Project with `.aidd/graphs/path-aliases.toon` | `aidd graphs list` shows `aliases` exactly once; without the file it is absent; with the file AND a charter row named `aliases`, only the charter row appears and the built-in is not added |
| AC-292 | `aidd graphs show aliases ordr` with the row `ordr_table.dart,oped_table.dart,mobile,F30` | one line `ordr_table.dart -> oped_table.dart [mobile] F30` |
| AC-293 | `show` with no match, with a missing file, and with binary file bytes | the three messages of FR-251; no exception |
| AC-294 | `to_graph` of two rows sharing an old name | 3 nodes, 2 edges; the same row twice gives one edge |
| AC-295 | `graph_explorer.py --graph x.toon --kind aliases --layer aliases --out y.html` | exit 0; `y.html` contains the three legend labels of FR-255, `RENAMED_TO`, `legend-aliases`, `insp-scope`, `insp-reason`, `aliases-empty-banner` |
| AC-296 | SUPERSEDED by AC-060 of the 004 amendment (JSON path) | — |
| AC-299 | Unified explorer of a project with the alias file (`graph_explorer.py --root R`) | a layer `aliases` with 4 nodes; `metric-aliases` and `layer-cb-aliases` present (registry-generated) |
| AC-297 | Task resolved by delete or by rename | the `progress` graph node has `state` = `deleted`/`renamed`; others have no `state` key |
| AC-298 | `y.html` | contains no `http://`, `https://` or `//cdn` reference and no external `<script src>`/`<link href>` (the general rule is AC-058 of the 004 amendment; kept here for the alias page) |

## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `python -m unittest discover -s tests -p "test_alias_graph.py" -v` | exit 0 | T-35, T-36, T-37, T-38, T-39, AC-291..AC-295, AC-297..AC-299 |
| V-2 | `python -m unittest tests.test_aidd_progress tests.test_progress_resolution -v` | exit 0 | T-39, FR-257 (no regression) |
| V-3 | `python -m unittest tests.test_dot_aidd_mirror -v` | exit 0 | T-40 |
| V-4 | `python -m unittest discover -s tests -p "test_unified_*.py" -v` and `python -m unittest discover -s tests -p "test_explorer_controls*.py" -v` | exit 0 (no regression of the 004 amendment) | T-38 |

Synthetic temporary directories only; no database, Docker or network.

## Visual source of truth (Step 0, R4)

| Codes | Blocks spec | Status | Mockup source |
|---|---|---|---|
| SCREEN-901 | 007-aidd-review-html-close-gate | resolved when the owner approves the mockup | `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.html` (local snapshot of the Stitch screen, SHA-256 recorded in `prototypes/alias-graph-explorer/alias-graph-explorer.sha256`) |

## Out of scope

Generating `path-aliases.toon`; the explorer base, its layer machinery and its controls (zoom, fit, centre, copy, theme: all owned by the 004 amendment); any Stitch call at runtime; changing the JSON path of the explorer; b1SycLink files.

## Open questions

None.

---

# Tasks — amendment 06

Every task prompt restates: scope in and out exactly as written; stop and report on any ambiguity; one responsibility per function; snake_case with a leading underscore for module-private helpers; design for failure (every file read in `try/except (OSError, UnicodeDecodeError, ValueError)`, fail closed); tool-first (mirrors by `cp`, never by hand); no databases, `db_verify.py` never run, no `aidd verify` by the builder. **UI rule:** T-38 builds a NEW view faithful to the approved mockup; it does not reuse legacy presentation.

Analysis parameters: `aidd size --files skill/scripts/alias_graph.py skill/scripts/aidd_graphs.py skill/scripts/graph_explorer.py skill/scripts/unified_graph.py skill/scripts/aidd_progress.py tests/test_alias_graph.py` → expected L (CLI and gate area, more than 8 files with mirrors).

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-35 | FR-250..FR-257, AC-291..AC-298 | `tests/test_alias_graph.py` | LOGIC | | | any production code; any other test file |
| T-36 | FR-252, FR-254 | `skill/scripts/alias_graph.py` | LOGIC | | | `aidd_graphs.py`, `graph_explorer.py`, any other module |
| T-37 | FR-250, FR-251 | `skill/scripts/aidd_graphs.py` | LOGIC | | | the `explorer` subcommand branch; any graph other than `aliases` |
| T-38 | FR-253, FR-255, SCREEN-901 | `skill/scripts/graph_explorer.py` + `skill/scripts/unified_graph.py` | VIEW-new | | | the JSON loading path; layer pill, checkbox and colour (registry-generated); every control of the 004 amendment |
| T-39 | FR-256, FR-257 | `skill/scripts/aidd_progress.py` | LOGIC | | | the `renamed` counting and the output format of `aidd progress` |
| T-40 | FR-250..FR-257 (mirror) | `adapters/dot-aidd/scripts/alias_graph.py` + `adapters/dot-aidd/scripts/aidd_graphs.py` + `adapters/dot-aidd/scripts/graph_explorer.py` + `adapters/dot-aidd/scripts/unified_graph.py` + `adapters/dot-aidd/scripts/aidd_progress.py` + `tests/test_dot_aidd_mirror.py` | LOGIC | | | any change that is not a byte copy of the T-36..T-39 files, except one list entry in the guard test |
| T-41 | FR-251, FR-253 docs | `skill/SKILL.md` | LOGIC | | | any other section; b1SycLink files |

## Per-task detail

### T-35 — failing tests first
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 80k
- Agent role: tests
- Model tier: medium
- Wave: 11

**Detail**
- Goal: encode AC-291..AC-295 and AC-297..AC-299 as unit tests that fail on the code left by the 004 amendment.
- Cites: FR-250..FR-257, AC-291..AC-295, AC-297..AC-299.
- Depends on: none in this amendment (runs after wave 10 of the 004 amendment).
- Read first: `skill/scripts/aidd_graphs.py` lines 140-181 and 889-917; `specs/004-aidd-graph-first/amendment-unified-explorer.draft.md` (FR-061, FR-067, T-75: the `--graph`, `--kind`, `--layer`, `--root` flags and `TOON_READERS`); `tests/test_aidd_progress.py` lines 1-30.
- Files to change: `tests/test_alias_graph.py` (new).
- Naming contract: class `AliasGraph(unittest.TestCase)` with methods `test_parse_and_load_rows`, `test_bad_file_gives_empty`, `test_to_graph_nodes_edges`, `test_show_prints_neighbours`, `test_registry_has_aliases_only_when_file_exists`, `test_explorer_accepts_toon`, `test_explorer_html_is_self_contained`, `test_unified_explorer_has_alias_layer`, `test_progress_graph_task_state`. Production names exercised: `alias_graph.parse_aliases(text)`, `alias_graph.load_aliases(path)`, `alias_graph.to_graph(rows)`, `alias_graph.show_aliases(root, query, limit=25)`, `aidd_graphs.show(root, name, query, limit=25)`, `aidd_graphs.load_registry(root)` (or the registry function at line 181, whichever the file exposes: read it), `graph_explorer.main(argv)`, `unified_graph.TOON_READERS`; registry-generated ids `metric-aliases`, `layer-cb-aliases`; alias-view ids `legend-aliases`, `insp-scope`, `insp-reason`, `aliases-empty-banner`.
- Behaviour:
  1. Header: `sys.path.insert(0, <repo>/skill/scripts)`, imports of the modules above (`alias_graph` will not exist yet: import it inside each test so each fails individually).
  2. Fixture text: `version: 1\ngenerated: 2026-11-03T00:00:00+00:00\naliases[2]{old,new,scope,reason}:\n  ordr_table.dart,oped_table.dart,mobile,F30\n  ocrd_table.dart,opar_table.dart,mobile,F30\n` written to `<tmp>/.aidd/graphs/path-aliases.toon`.
  3. `test_to_graph_nodes_edges`: those two rows give 4 nodes (ids `old:ordr_table.dart`, `new:oped_table.dart`, `old:ocrd_table.dart`, `new:opar_table.dart`) and 2 edges of type `RENAMED_TO`; a third row `ordr_table.dart,oped_table.dart,mobile,F30` repeated gives no new node and no new edge.
  4. `test_show_prints_neighbours`: `show_aliases(root, 'ordr')` equals `ordr_table.dart -> oped_table.dart [mobile] F30`; `'zzz'` gives `No alias matching 'zzz'.`; missing file and bytes `b'\xff\x00{'` give the FR-251 missing-file message and never raise.
  5. `test_explorer_accepts_toon`: `graph_explorer.main(['--graph', toon, '--kind', 'aliases', '--layer', 'aliases', '--out', html])` returns 0 and the html text contains `RENAMED_TO`, the three legend labels `old name`, `new name`, `renamed in progress`, and the ids `legend-aliases`, `insp-scope`, `insp-reason`, `aliases-empty-banner`.
  6. `test_explorer_html_is_self_contained`: the same html contains none of `http://`, `https://`, `//cdn`, `<script src`, `<link href`.
  7. `test_unified_explorer_has_alias_layer`: a temp project whose charter `## Graphs` table declares `aliases` (kind `aliases`, output `.aidd/graphs/path-aliases.toon`); `graph_explorer.main(['--root', root, '--out', html])` returns 0; the embedded payload has a layer `aliases` with 4 nodes and the html contains `id="metric-aliases"` and `id="layer-cb-aliases"`.
  8. `test_progress_graph_task_state`: a temp project with a `(delete)` task whose file is gone and a renumbered migration task; the progress graph returned by the module's graph writer has `state == 'deleted'` and `state == 'renamed'` on those two task nodes and no `state` key on a normal task.
  9. `test_registry_has_aliases_only_when_file_exists`: registry rows contain `aliases` with the file and do not contain it without.
- Tests first: this task IS the tests; run `python -m unittest discover -s tests -p "test_alias_graph.py" -v` and keep the red output (every test fails or errors on the current code except `test_explorer_html_is_self_contained`).
- Verify: `python -m unittest discover -s tests -p "test_alias_graph.py" -v` → red before T-36; exit 0 after T-39.
- Do NOT: touch production code; use a database, Docker or the network; weaken an assertion later.
- Done when: the 9 tests exist with exactly these names and the red run is recorded by the verifier.
- Size: ~130 changed lines.
- Open questions: none.

### T-36 — the alias reader module
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium
- Wave: 12

**Detail**
- Goal: one reader and converter for the alias format.
- Cites: FR-252, FR-254.
- Depends on: T-35.
- Read first: the tests created by T-35 in the file named in T-35's Files to change; `skill/scripts/aidd_progress.py` function `_load_aliases` (amendment 04) for the line format.
- Files to change: `skill/scripts/alias_graph.py` (new).
- Naming contract: constant `SECTION_RE = re.compile(r'^aliases\[(\d+)\]\{old,new,scope,reason\}:\s*$')`; functions `parse_aliases(text) -> list[dict]` (keys `old`, `new`, `scope`, `reason`), `load_aliases(path) -> list[dict]`, `to_graph(rows) -> dict`, `show_aliases(root, query, limit=25) -> str`, `is_alias_toon(text) -> bool`.
- Behaviour:
  1. `parse_aliases`: ignore every line that does not start with two spaces; split on `,` with maxsplit 3; keep rows with at least 2 non-empty fields; base names only (reject a field containing `/`, `\\`, NUL or `..`); `scope` and `reason` default to `''`.
  2. `load_aliases`: read UTF-8; any `OSError`, `UnicodeDecodeError` or `ValueError` returns `[]`.
  3. `to_graph`: exactly as FR-254; node ids unique; edges de-duplicated by `(source, target)`.
  4. `show_aliases(root, query, limit)`: path `<root>/.aidd/graphs/path-aliases.toon`; messages exactly as FR-251; at most `limit` lines.
  5. `is_alias_toon(text)`: true when any line matches `SECTION_RE`.
- Tests first: T-35 tests for this module are red before this task.
- Verify: `python -m unittest discover -s tests -p "test_alias_graph.py" -v` → the parse, load, to_graph and show tests pass.
- Do NOT: import from `aidd_graphs.py` or `graph_explorer.py` (they import this module, not the reverse); read any file other than the alias file; raise.
- Done when: the four named functions behave as listed and the related T-35 tests pass.
- Open questions: none.

### T-37 — registry entry and `show`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium
- Wave: 13

**Detail**
- Goal: make the alias graph a registered, queryable graph.
- Cites: FR-250, FR-251.
- Depends on: T-36.
- Read first: `skill/scripts/aidd_graphs.py` lines 140-181 (registry builder) and 889-917 (`show`).
- Files to change: `skill/scripts/aidd_graphs.py`.
- Naming contract: no new public names; the registry builder gets one new row and `show` one new branch calling `alias_graph.show_aliases` through the existing helper `_module("alias_graph")` (the pattern used for `component_graph` at line 904).
- Behaviour:
  1. In the registry builder, before `return out`, append the FR-250 row only when `(root / ".aidd" / "graphs" / "path-aliases.toon").is_file()`.
  2. In `show`, after the `ui` branch and before `_load_graph`, add: when `e["kind"] == "aliases"` return `alias_graph.show_aliases(root, query, limit)` (message if the module is missing: `alias_graph module not found`).
  3. No change for any other graph.
- Tests first: the T-35 tests `test_registry_has_aliases_only_when_file_exists` and `test_show_prints_neighbours` are red before this task.
- Verify: `python -m unittest discover -s tests -p "test_alias_graph.py" -v` → those two pass; `python -m unittest tests.test_aidd_graphs -v` → exit 0 (no regression).
- Do NOT: touch the `explorer` branch at lines 1118-1133; change refresh/status logic; add any other graph kind.
- Done when: `aidd graphs list` shows `aliases` only with the file and `show` answers as listed.
- Open questions: none.

### T-38 — explorer reads the alias graph and draws SCREEN-901
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: VIEW-new
- Size: M

**Estimate**
- Effort: High
- Agent min: 30
- Human ref hours: 1.5
- Tokens (est): 120k
- Agent role: builder
- Model tier: high
- Wave: 13

**Detail**
- Goal: the layer `aliases` (already a registry-generated layer of the unified explorer) gets the alias-specific view of the approved SCREEN-901 mockup, and the alias `.toon` gets its dedicated reader.
- Cites: FR-253, FR-255, SCREEN-901.
- Depends on: T-36 (and, outside this amendment, T-76, T-83 and T-84 of the 004 amendment).
- Read first: the APPROVED mockup `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.html` lines 1-60 (state tokens), 360-420 (legend, empty banner), 470-510 (details rows) and 800-910 (edge and node drawing), and `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.sha256`; `specs/004-aidd-graph-first/amendment-unified-explorer.draft.md` (FR-061, FR-064, FR-067, FR-072, T-76, T-83).
- Files to change: `skill/scripts/unified_graph.py` (one reader and one `TOON_READERS` entry), `skill/scripts/graph_explorer.py` (alias view only).
- Naming contract: in `unified_graph.py` the function `_read_aliases_toon(text)` (calls `_sibling("alias_graph")`, returns `to_graph(parse_aliases(text))`, raises `ValueError` when the module is missing) and the entry `TOON_READERS["aliases"] = _read_aliases_toon`; in `graph_explorer.py` the constant `ALIAS_LEGEND = ("old name", "new name", "renamed in progress")`, the JS function `renderAliasView()`, the CSS variables `--alias-old`, `--alias-new`, `--alias-prog` (dark values `#f85149`, `#3fb950`, `#d29922` in `:root`; light values `#d9383a`, `#1a7f37`, `#bf8700` in `:root.light`, all taken from the mockup tokens), element ids `legend-aliases`, `insp-scope`, `insp-reason`, `aliases-empty-banner`; node types `alias_old`, `alias_new`; edge relation `RENAMED_TO`; task-node attribute `state` (`renamed`, `deleted`). Registry-generated and NOT created here: `metric-aliases`, `layer-cb-aliases`, `--layer-aliases`.
- Behaviour:
  1. Register the reader in `unified_graph.py`; no other change there.
  2. Legend `legend-aliases`: shown only when the payload has a layer of kind `aliases`; exactly the three `ALIAS_LEGEND` labels with swatches `--alias-old`, `--alias-new`, `--alias-prog`, plus the text `Edge type: RENAMED_TO` (mockup lines 360-410 and 443).
  3. Canvas: nodes of type `alias_old` and `alias_new` use `--alias-old` and `--alias-new`; edges with relation `RENAMED_TO` get an arrowhead at the target and a `RENAMED_TO` badge at mid-edge, as in mockup lines 807-882; task nodes with `state` `renamed` use `--alias-prog`, `deleted` use `--alias-old`; other nodes unchanged.
  4. Inspector: for an alias node, two rows `insp-scope` and `insp-reason` filled with `textContent` from the node metadata `scope` and `reason` (mockup lines 470-500); hidden for other nodes.
  5. Empty state: when the `aliases` layer exists with 0 nodes or `missing` true, `aliases-empty-banner` shows "No aliases: the project has not generated .aidd/graphs/path-aliases.toon" (mockup line 415).
  6. Mechanical comparison: a test asserts that the mockup's legend labels, `RENAMED_TO`, the empty-state text and the dark and light state-token values appear in the generated HTML; differences are reported, never ignored. Zoom, fit, centre, copy and theme are NOT touched (004 amendment).
- Tests first: T-35 `test_explorer_accepts_toon` and `test_unified_explorer_has_alias_layer` are red before this task.
- Verify: `python -m unittest discover -s tests -p "test_alias_graph.py" -v` → exit 0; `python -m unittest discover -s tests -p "test_unified_*.py" -v` → exit 0 (no regression of the 004 amendment).
- Do NOT: create the layer pill, checkbox or layer colour (registry-generated); add or change any control; change the JSON input handling, other layers or node types; copy the legacy presentation of another view; add a dependency or CDN; call Stitch at runtime; use `innerHTML`.
- Done when: both Verify commands pass and the mechanical mockup comparison reports no difference.
- Size: ~110 changed lines.
- Open questions: none.

### T-39 — progress graph attributes and a single reader
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium
- Wave: 13

**Detail**
- Goal: expose resolved states in the progress graph and remove the duplicate alias reader.
- Cites: FR-256, FR-257.
- Depends on: T-36.
- Read first: `skill/scripts/aidd_progress.py` the graph writer that builds the progress graph task nodes (search `"type": "T"`), `_load_aliases` and `task_state`.
- Files to change: `skill/scripts/aidd_progress.py`.
- Naming contract: no new public names; add key `state` to task nodes only when the task state is `renamed` or the task is delete-only and satisfied (`deleted`); `_load_aliases(root)` returns the same `{old: new}` dict as before but obtained from `alias_graph.load_aliases`.
- Behaviour:
  1. Task node gets `state` as above; absent otherwise (a task with no resolution keeps its exact current dict).
  2. `_load_aliases` calls `alias_graph.load_aliases` and builds the dict from the rows; keeps the per-root cache.
- Tests first: T-35 `test_progress_graph_task_state` is red before this task; the amendment-04 tests (`test_progress_resolution.py`) must stay green.
- Verify: `python -m unittest tests.test_aidd_progress tests.test_progress_resolution -v` → exit 0, and the T-35 file → exit 0.
- Do NOT: change `task_state` results or the printed output of `aidd progress`; add dependencies.
- Done when: both commands pass.
- Open questions: none.

### T-40 — mirrors
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 25k
- Agent role: builder
- Model tier: medium
- Wave: 14

**Detail**
- Goal: keep the project bundle identical to the skill source.
- Cites: FR-250..FR-257 (mirror).
- Depends on: T-37, T-38, T-39.
- Read first: `tests/test_dot_aidd_mirror.py`.
- Files to change: `adapters/dot-aidd/scripts/alias_graph.py`, `adapters/dot-aidd/scripts/aidd_graphs.py`, `adapters/dot-aidd/scripts/graph_explorer.py`, `adapters/dot-aidd/scripts/unified_graph.py`, `adapters/dot-aidd/scripts/aidd_progress.py`, `tests/test_dot_aidd_mirror.py`.
- Naming contract: none new; each script target is a byte copy of its `skill/scripts` source; the guard list `VERBATIM_SCRIPTS` gains the entry `"alias_graph.py"`.
- Behaviour: five `cp` commands; then `cmp` each pair; then the one-line list insertion; no other hand edit.
- Tests first: `tests.test_dot_aidd_mirror` fails after T-36..T-39 until the copies exist.
- Verify: `python -m unittest tests.test_dot_aidd_mirror -v` → exit 0.
- Do NOT: edit any copy by hand; touch other mirrors.
- Done when: the mirror test passes.
- Open questions: none.

### T-41 — document
**Classify**
- Nature: `REQUIREMENT`
- Priority: 4
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 25k
- Agent role: docs
- Model tier: medium
- Wave: 14

**Detail**
- Goal: document the registered alias graph and its explorer view.
- Cites: FR-251, FR-253.
- Depends on: T-37, T-38.
- Read first: `skill/SKILL.md` the paragraph titled "Task state in `aidd progress` and `aidd pending`" and the `aidd graphs` description.
- Files to change: `skill/SKILL.md`.
- Naming contract: documents exactly: graph name `aliases`, kind `aliases`, file `.aidd/graphs/path-aliases.toon`, commands `aidd graphs show aliases <name>`, `aidd graphs explorer aliases` and `aidd graphs explorer` (the unified explorer shows it as the layer `aliases`), node types `alias_old` and `alias_new`, edge `RENAMED_TO`.
- Behaviour: add 3 lines after the paragraph named in Read first: registration, the three commands, the node and edge names.
- Tests first: no code; the check below exits 1 before this task and 0 after.
- Verify: `python -c "import sys; sys.exit(0 if 'RENAMED_TO' in open('skill/SKILL.md', encoding='utf-8').read() else 1)"` -> exit 0.
- Do NOT: change any other section; mention b1SycLink.
- Done when: the three lines exist and the check passes.
- Open questions: none.

## Removed tasks

T-42 (adopt the F47 explorer) was removed on 2026-11-03: superseded by T-74..T-76 of the 004 amendment.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 11 | T-35 | tests | 20 | 80 | 1 |
| 12 | T-36 | builder | 15 | 60 | 0.75 |
| 13 | T-37, T-38, T-39 | builder | 30 | 240 | 3 |
| 14 | T-40, T-41 | builder, docs | 5 | 50 | 0.5 |

Total agent time (critical path): 70 min
Total tokens (k): 430
Total human reference hours: 5.25
Tasks: 7 in 4 waves (computed by `waves.py` in the scratchpad from the task blocks). Wave 11 starts only after wave 10 of
`specs/004-aidd-graph-first/amendment-unified-explorer.draft.md`; no two tasks of one wave touch the same file.
