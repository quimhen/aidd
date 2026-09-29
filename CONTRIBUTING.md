# Contributing to AIDD

Thanks for looking at this. AIDD is early (see the README's "Status" section) and has a single
maintainer for now — small, well-scoped PRs are much easier to review than large ones.

## Getting set up

```bash
git clone https://github.com/quimhen/aidd.git
cd aidd
```

No install step is required to run the tests — the suite is stdlib-only `unittest`, zero
dependencies. If you also want the `aidd` CLI on your PATH: `pip install -e .`

## Running the tests

```bash
python -m unittest discover -s tests -v
```

This is exactly what `.github/workflows/test.yml` runs, on Python 3.10/3.11/3.12, on both
Ubuntu and Windows. Run it locally before opening a PR — CI runs the same command on every
push/PR to `main`.

If your change touches anything under `catalog/`, also run:

```bash
python skill/scripts/validate_catalog_entry.py --changed origin/main
```

`.github/workflows/catalog-validate.yml` runs this automatically on any PR touching
`catalog/**`, and validates every package on push to `main`.

## Repo structure

See the README's ["What's in this repo"](README.md#whats-in-this-repo) section for the full
breakdown (`skill/`, `aidd/`, `commands/`, `adapters/`, `catalog/`, `tests/`). The short version:
`skill/AIDD.md` is the tool-agnostic methodology core; everything else — the CLI, the Claude
Code commands, the other-tool adapters — is a thin layer that points back to it.

## What kind of change is this?

**Changing the methodology itself** (a pipeline step, the spec graph, a hook's behavior) —
edit `skill/AIDD.md` and/or the relevant script under `skill/scripts/` or `skill/hooks/`. If the
change affects what an adapter-generated command should say, check whether `commands/aidd-*.md`
or `generate_adapters.py`'s output needs to follow. Add or update a test under `tests/` that
exercises the actual behavior (mock any external call — network, `gh`/`az`/Bitbucket CLI, a real
tracker — never let a test touch a live service).

**Adding or fixing an adapter target or issue-tracker provider** — these are auto-discovered
extensions, not a dispatch table to edit. See [`docs/EXTENDING.md`](docs/EXTENDING.md) for the
`manifest.json` shape and where the code file goes (`skill/extensions/<id>/`). Mirror an
existing provider/adapter's test under `tests/` (e.g. `tests/test_extension_providers.py`,
`tests/test_generate_adapters.py`).

**Adding or fixing a charter checkable rule** — this one doesn't touch code at all: it's a row
in a project's own `charter.md` "Checkable rules" table, read by `check_charter.py`. Not
something you'd send a PR to this repo for, unless you're fixing a bug in `check_charter.py`
itself — in which case add a case to `tests/test_check_charter.py`.

**Adding a marketplace package** (a template, adapter, provider, or hook someone installs into
their own project via `aidd marketplace install`) — this does not go through this file. Follow
[`catalog/CONTRIBUTING.md`](catalog/CONTRIBUTING.md) instead; it covers picking an id,
`package.json`'s required fields, and `validate_catalog_entry.py`.

## What a PR needs

- Tests green locally (`python -m unittest discover -s tests -v`) — CI will re-run this on
  every OS/Python combination in the matrix regardless.
- A new test for new behavior, not just a passing existing suite.
- If you changed something `check_charter.py` or `check_spec.py` could plausibly flag against
  this repo's own `charter.md`/specs, run it and make sure you haven't introduced a violation.
- No changes bundled in from an unrelated concern — one PR, one change, same principle AIDD
  itself asks agents to follow ("one code, one file, one PR").

## Reporting a bug or proposing something bigger

Open an [issue](../../issues) first for anything that isn't an obvious small fix — a new
pipeline step, a change to the spec-graph format, a new hook — so we can agree on the approach
before you put the work in. For security issues, see [`SECURITY.md`](SECURITY.md) instead of
opening a public issue.
