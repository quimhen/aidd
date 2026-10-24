# AIDD core — read this file, not AIDD.md

Short on purpose (about 6 KB). `.aidd/AIDD.md` is ~120 KB and most hosts truncate a file read at
~50 KB or ~2000 lines, so reading it "in full" silently drops Steps 2-7. Never load it whole:
find the section you need and read only that range (see "Reading AIDD.md" below).

## 1. Detect your host from the tools you have

| Your toolset has | Host | Ask the user with | Dispatch a separate-context agent with |
|---|---|---|---|
| `AskUserQuestion` | Claude Code | `AskUserQuestion` | `Agent` / `Task` |
| `question` + subagent tool | OpenCode | `question` | the subagent tool |
| `write_to_file` + `replace_file_content` + `run_command` | Antigravity | plain text, then STOP and wait | a fresh session; else a separate pass over the diff. Gate: PreToolUse hook; check with `aidd doctor --host antigravity` |
| neither (Gemini CLI, Codex, Cursor, ...) | other | plain text, then STOP and wait | the host's sub-agent / a fresh session; else a separate pass over the diff without the implementer's reasoning |

Everywhere below, "ask" and "subagent" mean your row. The rules are identical on every host; only
who checks them differs.

## 2. Enforcement without hooks (OpenCode, Gemini, others)

Hooks that block writes exist only on Claude Code (and optionally elsewhere, see
`adapters/README.md`). When none is installed, YOU run the check. A rule you did not check is a
rule you broke.

| When | Run (exit 1 = FAIL, do not continue) |
|---|---|
| Session start | `aidd doctor` (gate installed?), `python .aidd/scripts/find_spec.py <keywords>`, then `aidd status` |
| Before the first code edit of a spec | `aidd rules check specs/<id>` — needs an approved `tasks.md` (R6) |
| After editing `spec.md`, `plan.md` or `tasks.md` | `python .aidd/scripts/check_spec.py specs/<id>` |
| After editing any SQL | `aidd sqlcheck <paths>` (static compile with the project's engine: `--engine postgres`, or `--cmd "<checker {file}>"` for another database); proceed on green. The ONE exhaustive database pass runs per wave (rule E8), never per file |
| Before saying a task is done | the task's verification (section 4), then mark its Status |
| Before ending the session | `aidd status`; close with `aidd rules close <id>` only after the owner says "Yes, close" |

Run `aidd next` before each step and follow its single next command.
OpenCode 2.x has no write hook: there enforcement is `aidd guard` via git hooks (`aidd install --githooks`);
`git commit --no-verify` is a known bypass, listed by `aidd status`.

Approval is the owner's, never yours: present the tasks, ask, wait. Where you cannot click, use the
review page: `aidd review specs/<id>`, then `aidd review specs/<id> --wait`; the owner approves in
the page; then run `aidd rules approve specs/<id>`. Fallback: the owner types
`Approve [tasks:<hash8>]` as a new message.
User quotes in `spec.md` (`user — "..."`) must be the owner's typed words: 5+ words, written after
the first `spec.md` draft, or 2+ words when quoting their answer to a question.
Never write `Approved:` yourself, never set `AIDD_RULES=off|warn` to get unstuck: if a gate blocks
the wrong spec, run `aidd rules activate <id>`.

## 3. The pipeline (one line each; details on demand)

State first: `AIDD intake: NEW SPEC | AMENDMENT | AMENDMENT — Fast Lane — <reason>`.

| Step | Do | Detail section in AIDD.md |
|---|---|---|
| -1 | `find_spec.py`: amend an existing spec, never duplicate | `### Step -1` |
| 0, 1, 1.5 | Only if there is a mockup: pin it, audit it into codes, draw the flow | `### Step 0`, `### Step 1` |
| 2 Align | Draft `spec.md`; ask the owner every open question; quote their words | `### Step 2` |
| 3 Plan | Map screen/API codes to files and names; a separate agent drafts it | `### Step 3` |
| 4 Tasks | One file per task, agent minutes + tokens, waves, then owner approval | `### Step 4` |
| 5 Build | One lane/agent per file group; builders only self-check statically | `### Step 5` |
| 6 Converge | `aidd verify`, then ONE independent auditor | `### Step 6` |
| 7 Doc | Mechanical handoff doc | `### Step 7` |

Backend/API/DB-only changes skip 0, 1, 1.5. A small contained change uses the Fast Lane.
Templates for every artifact: `.aidd/templates/` — copy, do not hand-write table headers.

## 4. Done means executed (non-negotiable on every host)

A task is NOT done because the code exists or reads right. Before marking a task done, run, and
cite the output or a screenshot saved under the spec dir:

1. **Static**: the project's typecheck/build/lint passes on what you touched. A new TypeScript
   error you introduced is not done.
2. **Behaviour**: the test, query, command or endpoint call that proves it. For SQL, run the
   function; `db reset` only proves it parses.
3. **Visual (any task with a screen and a mockup)**: build, run, capture the real screen and put
   it next to the mockup's screen (`SCREEN-nn`). Compare layout, header, sections, popups and
   spacing, not only that the page loads. The page must render without an error boundary.
4. Cannot run it? Write `not-verified`, give the owner a script to test by hand, and leave the
   task partial. Never write "done" for something you did not execute.

`check_spec.py` prints `STRUCTURAL CHECK ONLY`: zero gaps means the files are consistent, not that
anything works. `aidd verify specs/<id>` is what executes the spec's `## Verification` table.

## 5. Working rules that save the most time

- **Graph first, filter first.** Ask `find_spec.py` / `aidd graphs show <name> <query>` before
  opening source; `grep -n` and ranged reads, never `cat` a big file or an evidence log.
- **Tools before manual work (S1).** If a script, query or the `aidd` CLI can do it, estimate and
  use that. `aidd progress` measures implementation % with no LLM: do not write your own counter.
- **One agent per lane, one owner per file**, independent work in one message, long jobs in the
  background. Run `aidd pending specs/<id>` first and launch agents only for pending tasks.
- **Never run two builds at once** in the same working tree (file contention, worst on Windows
  with OneDrive); serialize them or use a separate worktree.
- **Do not touch `.aidd/`** (evidence, gate state, protected paths) and do not hand-edit
  `specs/index.toon`.
- **Mockups are requirements** (global rule): walk the mockup screen by screen; "reuse X" means
  reuse the logic/data and build a NEW view faithful to the mockup unless the task says
  `Kind: VIEW-legacy`.
- Never copy a secret into a file, spec, memory entry or command; refer to it by variable name.

## 6. Reading AIDD.md without truncation

```
grep -n "^### Step\|^## " .aidd/AIDD.md          # section map with line numbers
```
Then read ONLY the range you need with your file tool (`offset`/`limit`) or
`sed -n 'A,Bp' .aidd/AIDD.md` (PowerShell: `Get-Content .aidd/AIDD.md | Select-Object -Skip A-1 -First N`).
Read the "Hard rules" table (R1-R14) before writing `spec.md`/`tasks.md`; each rule names its fix.
If a read reports "showing lines 1-N of M" or ends mid-sentence, you have a fragment: continue
from the cut or read by section. Do not work from a fragment.

## 7. Resolve paths before running anything

`.aidd/` is the project copy. Run `ls .aidd/AIDD.md .aidd/scripts` first; if it is missing, stop and
tell the owner to run `aidd init <project>` instead of guessing a path. The `aidd` CLI is
`pip install aidd-cli`; if it is not on PATH call the script directly:
`python .aidd/scripts/<script>.py` (e.g. `aidd_rules.py`, `aidd_status.py`, `aidd_progress.py`).
