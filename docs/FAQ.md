# FAQ

Questions and answers about AIDD. Don't see yours? Open a
[GitHub issue](../../issues/new) or a [discussion](../../discussions).

## Is this a new AI agent I have to learn?

No. AIDD is not a tool to learn — it's a set of habits your existing AI coding assistant follows
for you. You keep using Claude Code, OpenCode, Codex, or Gemini CLI exactly as you do today; AIDD
changes what that assistant does before, during, and after it touches code.

## What does it actually stop happening?

- Your AI creating a new file/spec every time, even for a tiny fix, instead of reusing what's
  already there.
- Reviewing the same screen or feature more than twice for the same underlying reason.
- Nobody being sure which conversation or file has the "real" current requirements.
- Your AI referencing a screen, button, or database table that turns out not to exist.
- Different AI tools on the same team "knowing" different things about the project.

## Do I need to install anything new?

For Claude Code: copy `skill/` to `~/.claude/skills/aidd` and run
`python scripts/install_hooks.py` once. For OpenCode, Codex, or Gemini CLI: see
[`adapters/README.md`](../adapters/README.md) — each has a thin adapter that points back to the
same methodology core (`skill/AIDD.md`), so nothing is duplicated or relearned per tool.

## Does it work in any language?

The automatic prompt-level nudge (Claude Code) currently covers English, Spanish, Portuguese, and
a handful of literal Chinese trigger terms. Outside those, the pipeline still engages — Claude Code
matches the skill's own description semantically regardless of language, and the hard code-edit
gate doesn't read the prompt at all, so no request silently skips the pipeline for being in the
"wrong" language. Worst case, only the early nudge is missed.

## Is the "independent audit" real, or just a rule in a doc?

Both, depending on the tool. On Claude Code, it's an actual technical gate
(`hooks/require_independent_audit.py`): writing or updating `qa-audit.md` is blocked unless a
separate subagent was dispatched after the last code edit. On other tools it's the same rule,
followed the same way, without that specific lock yet — see
[`docs/PIPELINE.md`](PIPELINE.md#enforcement-hooks-installed-once-active-every-session) for exactly
what it can and can't verify.

## Are the token-savings numbers real?

Yes — measured, not estimated, by comparing what a plain read of the relevant spec files costs
against what AIDD's own lookup tools (`find_spec.py`, `check_spec.py`) report back, on a real
working project. The exact commands are in [`docs/WHY-AIDD.md`](WHY-AIDD.md) so anyone can
reproduce them on their own project. The percentage will differ by project size — that's expected.

## Does AIDD replace code review / human judgment?

No. It replaces the busywork of checking — searching for duplicates, re-reading whole files,
grading your own fix — so a person's judgment gets spent on what actually needs it, not on
bookkeeping.

## Is there a cost?

AIDD itself is free and open source (MIT license). If your team wants help adopting it, see
[`docs/CONSULTING.md`](CONSULTING.md) — no pricing is published there either; every engagement is
scoped individually, so reach out.

## Where do bugs or feature requests go?

[GitHub issues](../../issues) on this repo.
