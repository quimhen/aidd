# Extending AIDD

AIDD has always had extension seams — this page is where they're documented in one
place instead of scattered across module docstrings. Providers and adapter targets are
now real auto-discovery seams: drop a `manifest.json` + code file under
`skill/extensions/<id>/` (bundled with this repo) or `<project>/.aidd/extensions/<id>/`
(project-local, including anything `aidd marketplace install` copies in for a
`provider`/`adapter`/`hook` package) and it's picked up automatically — no code change
to this repo and no PR required for a project's own copy. `skill/scripts/
extension_registry.py` is the authoritative reference: its module docstring documents
the full manifest shape, and `discover()`/`get_providers()`/`get_adapter_targets()`/
`get_hooks()` are what actually load these at runtime. The marketplace (see `catalog/`)
is the distribution layer on top of this — see `catalog/README.md` for publishing and
installing a package; this page covers what a package (or a hand-written project-local
extension) actually has to contain.

## 1. Provider and adapter extensions — manifest.json shape

Every extension is one folder with a `manifest.json` (plus its code file(s)) at
`skill/extensions/<id>/` or `<project>/.aidd/extensions/<id>/`. A project-local
extension with the same `(kind, id)` as a first-party one shadows it.

Required fields, every kind: `id`, `name`, `description`, `version`, `kind` (one of
`provider`, `adapter`, `hook`). Optional: `enabled` (default `true` — see
`aidd extensions enable/disable`).

Kind-specific fields:

- **`kind: "provider"`** — an issue-tracker provider. `entry`: the Python file in this
  folder implementing the provider contract (functions, not a class hierarchy):

  ```python
  def add_provider_args(parser): ...               # register this provider's own CLI flags
  def available(args) -> (bool, str | None): ...    # can this provider actually run?
  def create_issue(title, body, args, apply: bool) -> str | None: ...
  ```

  Dispatched by `tasks_to_issues.py --provider <id>` (`aidd tasks-to-issues ... --provider
  <id>`), which calls `extension_registry.get_providers()` to load every enabled provider
  extension by `id` instead of importing a fixed module list. See
  `skill/extensions/github/`, `skill/extensions/azure_devops/`, and
  `skill/extensions/bitbucket/` for the three first-party providers as worked examples.

- **`kind: "adapter"`** — one multi-agent command-file target, rendered by
  `generate_adapters.py` (via `extension_registry.get_adapter_targets()`, which replaces
  the old `TARGETS` dict lookup). An `adapter` object with: `dir`, `format` (`"markdown"`
  or `"toml"` — add a new render function to `generate_adapters.py`'s `_RENDERERS` dict
  if a target needs a third format), `filename`, `arg_placeholder`, `invoke_phrase`,
  optional `frontmatter_extra`. See `skill/extensions/adapters/cline/manifest.json` (or
  any of its four siblings under `skill/extensions/adapters/`) as a worked example.

- **`kind: "hook"`** — a Claude Code enforcement/advisory hook. An `events` list of
  `{"event", "matcher", "script"}` entries, consumed by `extension_registry.get_hooks()`.

To add a first-party provider or adapter target: create
`skill/extensions/<id>/manifest.json` (+ its code file) implementing the shape above,
and add a test under `tests/` mirroring the existing provider/adapter extension tests
(mock the network/CLI call, never let a test touch a real tracker). No dispatch table or
`TARGETS` dict to edit — `extension_registry.discover()` finds it by scanning
`skill/extensions/**/manifest.json`. To add a project-local one (no PR to this repo at
all), drop the same two files under `<project>/.aidd/extensions/<id>/` directly, or
publish it as a catalog package and let `aidd marketplace install <id>` copy it there.
Manage what's discovered with `aidd extensions list|info <id>|enable <id>|disable <id>`.

## 2. Charter checkable rules

Not code at all — `charter.md`'s own "Checkable rules" table
(`Rule | Type (forbidden/required) | Pattern | Applies to (glob)`), run by
`check_charter.py`. This is the one extension point every AIDD *user* (not just a
contributor to this repo) already has: a project adds its own rows without touching
any script.

## What these are not

Provider and adapter extensions (and hooks) *are* now a real plugin-loading mechanism:
`extension_registry.discover()` scans `skill/extensions/**/manifest.json` and
`<project>/.aidd/extensions/**/manifest.json` on every run and loads whatever it finds,
with no dispatch table, `TARGETS` dict, or import list to edit and no PR required for a
project's own extension. What this *isn't* is a sandboxed or reviewed plugin runtime —
a `manifest.json` + code file is `exec`'d as trusted Python (`get_providers()` uses
`importlib` to load and run the entry file directly), so only install a project-local
or marketplace extension whose code you'd otherwise be comfortable reviewing and
running yourself; there's no capability restriction or isolation beyond that. Charter
checkable rules stay data-only (a table row, never executed code) and remain the one
seam with no trust implications at all.
