"""aidd issue-tracker providers — one small stdlib-only module per tracker,
dispatched by tasks_to_issues.py's --provider flag. Not a plugin system: this
is the fixed, closed set AIDD ships with (github, azure_devops, bitbucket),
following spec-kit's own multi-provider precedent (its git/github extensions)
for *which* trackers matter, not its extension/catalog machinery — AIDD has
no marketplace, so "extensibility" here means "one more module in this
folder that matches the same two-function contract", not an installable
package.

Contract every provider module implements (functions, not a class hierarchy —
consistent with every other aidd script's stdlib-only, no-shared-base-class
style):
    available(args) -> (bool, str | None)
        Checks the provider's CLI/credentials are usable. Returns
        (True, None) or (False, "human-readable reason").
    create_issue(title, body, args, apply: bool) -> str | None
        Same contract as tasks_to_issues.py's original create_issue(): a
        dry run (apply=False) returns None without side effects; apply=True
        actually creates the issue and returns a URL/reference string, or
        None (with a message on stderr) on failure.
    add_provider_args(parser)
        Registers this provider's own CLI args (e.g. --org/--project for
        Azure DevOps, --workspace/--repo-slug for Bitbucket) on the shared
        argparse parser. A provider with no extra args (github) can register
        nothing.
"""
