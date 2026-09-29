# Security Policy

## Reporting a vulnerability

Please report security vulnerabilities privately, **not** in a public issue. Use GitHub Security
Advisories for this repository:

**https://github.com/quimhen/aidd/security/advisories/new**

This opens a private advisory visible only to you and the maintainer, and lets us coordinate a
fix and a disclosure timeline before anything becomes public. If you're unsure whether something
qualifies, report it anyway — a false positive costs a few minutes; a missed real issue doesn't.

We don't currently have a dedicated security contact email — the Security Advisories link above
is the supported channel until one exists.

## Supported versions

AIDD is at `0.1.0` and explicitly "Early" (see the README's Status section) — there is no LTS or
multi-version support policy yet. In practice, only the latest commit on `main` is supported;
please reproduce against `main` before reporting, and expect fixes to land there rather than as
a backport to a tagged release.

## Scope and what to look at

AIDD is a methodology plus a set of scripts/hooks that run with the same privileges as whatever
agent or terminal invokes them — there's no sandboxing beyond what's described here. Relevant
surface to keep in mind when reporting:

- **Claude Code hooks** (`skill/hooks/*.py`) run automatically on session/tool events with
  whatever privileges the Claude Code process has. A bug here could mean a hook fires when it
  shouldn't, or fails to gate an action it's meant to block (e.g. the independent-audit or
  graph-coherence gates).
- **Issue-tracker providers** (`skill/extensions/github/`, `skill/extensions/azure_devops/`,
  `skill/extensions/bitbucket/`, and any project-local or marketplace-installed provider under
  `.aidd/extensions/`) read credentials for `gh`/`az`/Bitbucket from environment variables and
  call out to those services on your behalf via `tasks_to_issues.py` / `aidd tracker sync`. A
  credential-handling bug here is high severity.
- **Marketplace packages** (`catalog/packages/<id>/`) are `exec`'d as trusted Python once
  installed into a project (see [`docs/EXTENDING.md`](docs/EXTENDING.md), "What these are not").
  `validate_catalog_entry.py` and CI (`.github/workflows/catalog-validate.yml`) only check
  structure and flag suspicious patterns (network calls, `subprocess`/`eval`/`exec`) for a human
  reviewer — they are not a sandbox. If you find a package that got past review with malicious or
  unsafely-written code, report it as a vulnerability rather than opening a public issue against
  the package.
- **Any script invoked by a hook or by the `aidd` CLI** that takes file paths or shell arguments
  derived from user/project content (e.g. `check_charter.py`'s glob patterns, `marketplace.py`'s
  install paths) — path traversal or injection here is in scope.

Thanks for helping keep this project and the projects that install it safe.
