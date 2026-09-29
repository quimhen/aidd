# Extending AIDD

AIDD has always had extension seams — this page is where they're documented in one
place instead of scattered across module docstrings. Until now these were closed,
first-party-only seams (add a module to this repo, submit a PR). The marketplace
(see `catalog/`) adds a fourth, third-party-facing seam on top — see `catalog/README.md`
for that one. The three below stay the internal, no-catalog-required way to extend a
project's own copy of AIDD, or to propose a first-party addition to this repo.

## 1. Issue tracker providers

`skill/scripts/providers/` — dispatched by `tasks_to_issues.py --provider <name>`.
Contract (functions, not a class hierarchy — see `providers/__init__.py`'s own
docstring for the authoritative version):

```python
def add_provider_args(parser): ...          # register this provider's own CLI flags
def available(args) -> (bool, str | None): ...   # can this provider actually run?
def create_issue(title, body, args, apply: bool) -> str | None: ...
```

To add one: create `skill/scripts/providers/<name>_provider.py` implementing the three
functions, register it in `tasks_to_issues.py`'s provider dispatch table, and add a test
file under `tests/` mirroring `tests/test_providers.py`'s style (mock the network/CLI
call, never let a test touch a real tracker).

## 2. Multi-agent adapter targets

`skill/scripts/adapter_targets.py` — one dict entry per agent tool, rendered by
`generate_adapters.py` (see that module's own docstring for why this is a data table
and not a class hierarchy). Fields: `name`, `dir`, `format` (`"markdown"` or `"toml"` —
add a new render function to `generate_adapters.py`'s `_RENDERERS` dict if a target
needs a third format), `filename`, `arg_placeholder`, `invoke_phrase`, optional
`frontmatter_extra`.

To add one: add an entry to `TARGETS`, then extend `tests/test_generate_adapters.py`'s
`TestGenerate.test_every_registered_target_generates_without_error` will pick it up
automatically (it iterates `TARGETS`) — add a target-specific assertion only if the new
format needs one beyond "generates without error."

## 3. Charter checkable rules

Not code at all — `charter.md`'s own "Checkable rules" table
(`Rule | Type (forbidden/required) | Pattern | Applies to (glob)`), run by
`check_charter.py`. This is the one extension point every AIDD *user* (not just a
contributor to this repo) already has: a project adds its own rows without touching
any script.

## What these are not

None of the three above are a plugin-loading mechanism — there's no "drop a file in a
folder and AIDD picks it up automatically" for providers or adapter targets; both
require a code change in this repo (or a fork of it) and a PR. That boundary was
deliberate for a single-maintainer skill; `catalog/README.md` is where a third party
now goes to publish something without forking.
