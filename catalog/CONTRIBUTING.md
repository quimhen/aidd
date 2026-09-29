# Submitting a marketplace package

1. **Pick an id.** Lowercase, digits, hyphens, 2–64 chars (`^[a-z0-9][a-z0-9-]{1,63}$`).
   Check it's not already taken: `python ../skill/scripts/marketplace.py search <id>`.
2. **Create the folder:**
   ```
   catalog/packages/<id>/
   ├── package.json
   └── files/
       └── ... your actual content ...
   ```
3. **Write `package.json`** — see [`schema.json`](schema.json) for the exact fields.
   Required: `id`, `name`, `description`, `version` (semver `X.Y.Z`), `author`,
   `license`, `kind` (`template`/`adapter`/`provider`/`hook`), `files` (a map of
   *destination path in the installing project* → *source path relative to your
   `files/` folder*).
   - `provider`/`hook` kinds install like any other: your `files` map must land a
     runtime `manifest.json` (shaped per `skill/scripts/extension_registry.py`'s
     docstring) plus your code/script file(s) together under `.aidd/extensions/<id>/`
     in the installing project, so `extension_registry.py` auto-discovers it after
     install.
4. **Add your id to `catalog.community.json`** — do not touch `catalog.json`, that
   one's first-party only:
   ```json
   { "id": "your-id" }
   ```
5. **Validate locally before opening the PR:**
   ```bash
   python ../skill/scripts/validate_catalog_entry.py <your-id>
   ```
   Fix every structural error it reports. It may also print security-review flags
   (network calls, `subprocess`/`eval`/`exec` usage) — these don't fail the check, but
   read them: a reviewer will ask about anything on that list, so addressing it in your
   PR description up front is faster than a review round-trip.
6. **Open a PR.** `.github/workflows/catalog-validate.yml` runs the same validator
   against your changed package automatically. A maintainer reviews the actual content
   of `files/` by hand before merging — this is not, and isn't meant to be, a fully
   automated accept path (see `catalog/README.md`'s last section for why).

## What gets rejected on sight

- Anything that writes outside the destination paths it declared in `package.json`.
- A `files` entry whose source path resolves outside the package's own `files/` folder
  (path traversal) — `validate_catalog_entry.py` checks this mechanically.
- Code that impersonates AIDD's own first-party output, or that silently phones home
  to a third-party service not disclosed in `description`.
- A `provider`/`hook` package that reads credentials from anywhere other than an
  environment variable (never a CLI flag — see `azure_devops_provider.py` /
  `bitbucket_provider.py` for the pattern every first-party provider already follows).

## Updating an existing package

Bump `version` in `package.json`, keep the same `id`. There is no separate "upgrade"
command — a project re-runs `marketplace.py install <id> --force` to pick up the new
version (its manifest simply records the new file hashes).
