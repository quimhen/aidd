# AIDD marketplace

Third-party-facing extension point, on top of the three internal ones documented in
[`docs/EXTENDING.md`](../docs/EXTENDING.md). A package here is installed into *your own
project* (not into this repo, not into AIDD's own skill folder) via
`aidd marketplace install <id>` — no fork required.

This exists for the same reason spec-kit has one, kept to the load-bearing parts only
(see [`skill/scripts/marketplace.py`](../skill/scripts/marketplace.py)'s own docstring
for exactly what was kept vs. dropped from that mechanism, and why).

## What a package is

One folder under `packages/<id>/`:

```
catalog/packages/<id>/
├── package.json     # metadata + files map — see schema.json
└── files/           # the actual content, referenced from package.json's "files"
```

`package.json` must validate against [`schema.json`](schema.json). The four `kind`
values and what installing each one actually does:

| kind | Installed how | Status |
|---|---|---|
| `template` | File copy into the target project | Installable now |
| `adapter` | File copy into the target project (a native command file for an agent tool) | Installable now |
| `provider` | File copy into `.aidd/extensions/<id>/` in the target project (manifest.json + code) | Installable now |
| `hook` | File copy into `.aidd/extensions/<id>/` in the target project (manifest.json + code) | Installable now |

`provider`/`hook` packages install the same generic way as any other kind — the
package's own `files` map is what points its `manifest.json` and code/script file(s)
at `.aidd/extensions/<id>/` in the target project. Once those files land,
[`skill/scripts/extension_registry.py`](../skill/scripts/extension_registry.py)
auto-discovers anything under `.aidd/extensions/**/manifest.json`, so the extension is
live with no further wiring. See that module's own docstring for the manifest.json
shape a `provider`/`hook` package must ship.

## Using it

```bash
python skill/scripts/marketplace.py list
python skill/scripts/marketplace.py search <query>
python skill/scripts/marketplace.py install <package-id> <project-root>
python skill/scripts/marketplace.py remove <package-id> <project-root>
```

Or via the CLI once `pip install -e .` is done: `aidd marketplace list/search/install/remove`.

Install records what it wrote in `<project-root>/.aidd/marketplace-manifest.json`, each
file content-hashed — `remove` only deletes a file whose hash still matches what was
installed (a hand-edited file is left alone and reported, not silently discarded; pass
`--force` to remove it anyway).

## Submitting a package

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Two catalogs, one merged list

- `catalog.json` — first-party, maintained by this repo's own maintainers.
- `catalog.community.json` — third-party submissions, reviewed the same way any other
  PR to this repo is (see CONTRIBUTING.md) before being merged into it.

A package id must be unique across both — `validate_catalog_entry.py` enforces this,
and CI runs it on every PR touching `catalog/`.

## What this is not

Not a fully automated accept path: `.github/workflows/catalog-validate.yml` checks
structure and safety-relevant shape (schema conformance, no path traversal, unique
ids) and flags content worth a human's attention — it does not, and cannot, decide
whether a submission's code is safe to run. A maintainer reviews and merges every
catalog addition by hand, same as spec-kit's own actual model for its extension
catalog.
