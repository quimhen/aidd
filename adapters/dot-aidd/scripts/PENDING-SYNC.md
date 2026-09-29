# Pending mirror: sync_issues.py / link_pr_to_task.py

`adapters/dot-aidd/scripts/` is a hand-maintained mirror of `skill/scripts/`
(same mechanism `check_spec.py`, `check_charter.py`, and `tasks_to_issues.py`
already use here — a plain copy-paste, not an automated sync script; see
`adapters/README.md`'s Tier 1 description). `aidd init` (`aidd/cli.py`'s
`cmd_init`) copies this whole folder verbatim into
`<project>/.aidd/scripts/`, so anything a project's own CI needs to run
locally (no network access back into this repo) has to live here too, not
just under `skill/scripts/`.

`skill/scripts/sync_issues.py` and `skill/scripts/link_pr_to_task.py` now
exist (contract-v2 providers: `get_status`/`link_pr`), and
`skill/templates/ci/github-actions-aidd.yml` /
`azure-pipelines-aidd.yml` both invoke
`.aidd/scripts/link_pr_to_task.py --apply` — but a straight copy-paste of
just these two files into this folder would NOT work standalone, so it was
deliberately not done yet:

- Both files `import extension_registry` and (`link_pr_to_task.py` only)
  `import tasks_to_issues as t2i` — neither is optional at import time.
  `extension_registry.py` (the provider/adapter/hook discovery module) is
  not mirrored anywhere under this folder at all today.
- `adapters/dot-aidd/scripts/tasks_to_issues.py` is itself a **stale**,
  pre-provider-registry copy of `skill/scripts/tasks_to_issues.py` (single
  hardcoded GitHub/`gh`-only implementation, predating the
  `extension_registry`-based multi-provider dispatch and the
  `update_task_column`/`find_header_index` helpers `link_pr_to_task.py`
  calls). This drift already existed before this task, independent of the
  two new files — see this same file's own history for `check_charter.py`,
  which has the identical kind of drift.

So landing these two files here for real needs, together, in one pass:

1. Copy `skill/scripts/extension_registry.py` into this folder (it has no
   dependency of its own beyond `SKILL_EXTENSIONS_DIR`, which would need to
   point at a project-appropriate extensions root when running from
   `.aidd/scripts/` rather than `skill/scripts/` — check whether it should
   resolve relative to `<project>/.aidd/extensions/` only, since
   `skill/extensions/` bundled-with-AIDD-itself is a concept that doesn't
   exist inside a project's own `.aidd/` copy).
2. Replace `adapters/dot-aidd/scripts/tasks_to_issues.py` with the current
   `skill/scripts/tasks_to_issues.py` (bringing it up to the provider-based
   contract) — a larger, deliberate change to an existing mirrored file,
   not a drive-by fix bundled into an unrelated task.
3. Only then copy `skill/scripts/link_pr_to_task.py` and
   `skill/scripts/sync_issues.py` in as new files.
4. Delete this file once all four are in place and a project that ran
   `aidd init` can actually run
   `.aidd/scripts/link_pr_to_task.py --apply` without an ImportError.

Until then, the CI templates' "Link PR to task" step degrades gracefully —
it checks `[ -f ".aidd/scripts/link_pr_to_task.py" ]` first and treats a
missing file as a skipped no-op, not a build failure — but a project that
wants that step to actually do anything needs to copy
`skill/scripts/{extension_registry.py,tasks_to_issues.py,
link_pr_to_task.py,sync_issues.py}` into its own `.aidd/scripts/` by hand
until this mirror is completed.
