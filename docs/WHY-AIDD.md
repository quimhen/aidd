# Your AI writes fast. Does it check its work before you have to?

*A methodology for working with AI coding agents.*

AIDD is a set of rules your AI coding assistant follows automatically. Before it builds anything,
it checks what already exists, plans it out loud, and gets a second, independent check before you
ever see the result — so you stop being the one who catches the mistakes.

## Sound familiar?

> "I asked it to fix one button. It rewrote half the screen and I had to figure out what changed."

Without a plan the AI checks itself against, "fix this" becomes "guess what else might need fixing
too."

> "I've reviewed this same screen three times this month for basically the same reason."

Mistakes found after the code is written cost a redo. AIDD finds them while the plan is still just
a plan.

## Six things you'll actually notice

Not features. Things that stop happening to you.

- **It looks before it leaps.** Before building anything new, it checks whether the work already
  exists somewhere — so you don't end up with three half-finished versions of the same thing.
- **Mistakes get caught early.** Gaps and unclear requirements are found while planning — as a
  question for you — instead of after the code is already written and reviewed.
- **Small, easy-to-check changes.** Work is broken into small pieces, one at a time. A mistake
  costs one small fix, not a giant change you have to untangle.
- **A real second opinion.** The rule is that review is never done by whoever built it — never the
  AI grading its own homework. On Claude Code, that's not just a rule the AI is supposed to
  follow: a technical check actually blocks the write-up until a separate reviewer has run. On
  other assistants, it's the same rule, followed the same way, without that specific lock yet.
- **Matches the design, first try.** Every screen and button is checked against the actual design
  before it's called finished — not "close enough," an actual side-by-side comparison.
- **Works with whatever AI you use.** Claude, OpenCode, Codex, Gemini — same rules, same
  discipline, no matter which assistant is doing the typing.

## Less re-checking means a cheaper, faster AI session

"Tokens" are what an AI session costs, roughly the way minutes cost on a phone plan. Fewer tokens
to do the same check means a faster answer and a smaller bill. These two numbers are measured — run
on a real, working project, not estimated:

| Check | Without AIDD | With AIDD | Reduction |
|---|---|---|---|
| Re-reading, before starting new work | 4,598 tokens | 316 tokens | 94% |
| Re-checking, before a human review | 3,548 tokens | 132 tokens | 97% |

Reproduce it yourself, on any project already using AIDD:

```bash
# Step -1 search
wc -c specs/<candidate-spec-1>/*.md specs/<candidate-spec-2>/*.md   # manual-read baseline
python .aidd/scripts/find_spec.py <keywords> | wc -c                # AIDD's context cost

# Step 6 gap-check
wc -c specs/<spec-folder>/*.md                                      # manual-read baseline
python .aidd/scripts/check_spec.py specs/<spec-folder>/ | wc -c     # AIDD's context cost
```

The percentages will move slightly as a project's own files change — that's expected, and the
point: they're live measurements, not a fixed marketing claim. (They were 90%/96%, then 93%/98%,
now 94%/97%, as the reference project's own specs grew.)

**Why this compounds.** Step −1 runs on every requirement, every fix, every "can you also…" — not
once per feature. A larger project doesn't make `find_spec.py`'s output much bigger (it's still one
ranked match + a handful of evidence lines); it makes the manual-read alternative *much* bigger.
The gap between the two widens as the project grows, not the other way around.

## Precise requirements mean fewer trips back to QA

Most testing time isn't spent finding bugs — it's spent finding the *same* mismatch a second or
third time, because it was never written down precisely enough to catch before the code existed.
AIDD writes it down first.

**Without precise requirements:** build from a loose description → QA tests it → doesn't match what
was meant → back to dev, rebuild, retest — repeat until it matches.

**With AIDD:** every screen, button, and rule written down precisely, up front → gaps questioned
before building → build → QA checks it against that same precise spec, once.

**Real example.** Auditing an existing lock screen against its own written requirement
("re-authenticates the session"), AIDD's audit step found that unlocking only checked the password
and code fields weren't *empty* — neither was actually verified against anything. Any non-empty
password and any 4-digit code unlocked the session. Not something a "looks fine" glance at the
running screen would ever catch, since the screen looked and behaved exactly as intended. The
password check is now real — fixed the same day it was found. The first re-check of that fix was
done by the same AI that wrote it, which is exactly the mistake this methodology exists to prevent
— caught, and turned into the technical lock described above, the same day, on the same project.

## It remembers your project, so it doesn't re-learn it every time

Close the laptop, come back tomorrow — or hand it to a teammate. Without a map, the AI has to
re-read the project from scratch just to get its bearings, every single time. AIDD keeps a small,
always-current map, so it picks up exactly where things were left off instead.

**Without a saved map:** new session opens → re-reads the whole project to figure out what's going
on → finally starts working.

**With AIDD:** new session opens → checks the small saved map → already knows what's done, what's
next, and how the pieces connect.

The "map" is two things AIDD keeps up to date automatically: a short note on what's active and
what's next (`STATE.md`), and a searchable index of how every screen, feature, and requirement
connects to the others (`specs/index.toon`). Neither is something you maintain by hand — both
rebuild themselves as the project changes.

## Is this actually for you?

If two or more of these sound like your week, it is:

- Your AI tool creates something new every time, even for a tiny fix, instead of reusing what's
  already there.
- You've reviewed the same screen or feature more than twice for basically the same reason.
- Nobody on the team is sure which conversation or file has the "real" current requirements
  anymore.
- You've caught your AI referencing a screen, button, or database table that turned out not to
  actually exist.
- Your team uses more than one AI coding tool, and each one seems to "know" different things about
  the project.

If any of that felt familiar, AIDD is built for exactly this problem — not a new tool to learn, a
set of habits your existing AI assistant follows for you.

## What actually happens, in one line

Every request goes through the same short routine before any code gets written:

**Check what exists → Plan it out loud → Build it in small pieces → Independent review → Compare
to the design**

See [`docs/PIPELINE.md`](PIPELINE.md) for the full technical breakdown.

## The honest fine print

- The percentages above are real, re-measured on a real working project — not a promise about your
  exact project, which may see more or less depending on its size.
- We don't claim a measured "X% faster" for actual developer time — that would need a proper study
  across many people, which this doesn't have. The time savings come from a reasoned explanation
  (fewer redo cycles, smaller reviews), backed by a real example, not a stopwatch.
- AIDD doesn't replace human judgment — it replaces the busywork of checking, so a person's
  judgment gets used on what actually needs it.
