# The perpetual improvement agent (design)

Status: design, not yet running. Tracks issues #23 (this document) and #24 (implementation).

## Goal

Two things the owner asked for on 2026-09-26:

1. **An agent that can be reached remotely** to ask about the project and give it instructions,
   without sitting at the development machine.
2. **A daily unattended run** that advances the improvement plan in `docs/STATUS-2026-09-26.md`
   one step at a time, leaving a reviewable trail.

## Mechanism

Claude Code **cloud routines** (https://claude.ai/code/routines). A routine spawns an isolated
cloud session on a cron schedule (minimum interval one hour) or once at a set time, with a
fresh clone of named GitHub repositories and an optional set of connectors. Facts that shape the
design:

- The session starts with **zero context**. Everything it needs must be in the prompt or in the
  repository. This is why `CLAUDE.md`, `docs/README.md`, `docs/STATUS-*.md` and `docs/SPEC.md`
  exist and why every PR must keep them current: they are the agent's memory.
- It runs in Anthropic's cloud, not on the owner's machine. No access to the local venv, to
  `PASTACOIN_GH_TOKEN`, or to local files. GitHub access is granted to the cloud environment
  separately (the routine's repository sources), so the pastacoin org must authorise that app
  or a deploy token before the first run.
- Available connectors on this account today: Google Drive (whitepaper), Claude Docs, Gmail,
  Google Calendar. Drive is the only one the daily run needs (read the whitepaper when a
  design question comes up). Gmail could carry the daily summary if the owner wants email.
- An environment named `Default` (`env_01Cu9aryXod1EumWUsZJC4Sy`, Anthropic cloud) exists.
- Model: default `claude-sonnet-5` for the daily run (cheap, adequate for scoped issues);
  `claude-opus-5-5` when a run is expected to touch design (Phase 2 controller work).

The "remote interaction" half is covered by the same infrastructure: the owner can open a Claude
Code cloud session on the repository from a phone or browser at any time, and it will read the
same documents. No custom chat bot is needed for v1. A Slack or Telegram front door can come
later if the browser is too much friction.

## The daily run

Schedule: once a day at 06:00 America/Denver (12:00 UTC; 13:00 UTC in winter), so a PR is
waiting when the owner wakes up. Cron: `0 12 * * *`.

Prompt outline (the real prompt lives in `tools/agent/daily_prompt.md` once #24 lands, so it
is versioned with the code):

1. Read `CLAUDE.md`, `docs/README.md`, `docs/STATUS-2026-09-26.md`, `docs/SPEC.md`, and, if the
   chosen issue is Phase 2, `docs/SIMULATION-RESULTS.md`.
2. Run `python -m pytest -q`. If main is red, the only allowed task is fixing it.
3. List open issues. Pick the lowest-numbered open issue in the **current phase** (the earliest
   phase that still has open issues), skipping any labelled `needs-owner` or `blocked`.
4. Implement it on a branch named `agent/<issue-number>-<slug>` with tests. Keep the diff
   focused on that issue.
5. Update the STATUS changelog, `docs/README.md` if a document was added or changed, and
   `docs/SPEC.md` if an enforced rule changed.
6. Open a PR that references the issue (`Closes #N`), with a test plan. Do **not** merge.
7. Post a five-line summary as a PR comment and, if the Gmail connector is attached, email it.

Guard rails, in priority order:

- **Never merge.** The owner merges. CI must be green before a PR is even worth a look.
- **Never edit the whitepaper** or any Drive document. Drive is read-only for the agent.
- **One issue per run.** If the issue turns out to need a decision (it changes a rule in
  `SPEC.md`, or the memo shows two defensible options), stop, write the options as a PR comment
  or an issue comment, label the issue `needs-owner`, and end the run without code.
- **No new dependencies** without an issue comment explaining why.
- **No force pushes, no history rewrites, no changes to `.github/workflows`** unless the issue
  is explicitly about CI.
- **Budget:** if the run has not opened a PR after roughly two hours of work, push the branch
  as a draft PR with a "where I got to" note and stop.

## Kill switch and dry run

- Disabling the routine at https://claude.ai/code/routines stops the next fire; a run already
  in progress finishes.
- A repository file `tools/agent/PAUSE` (any content) makes the run exit at step 1 with a
  comment on the tracking issue. This lets the owner pause from a phone by committing one file.
- `tools/agent/daily_prompt.md` can contain the line `MODE: dry-run`, in which case the run
  does steps 1 to 3, writes its plan as a comment on the chosen issue, and stops.

## Observability

- Every run leaves a PR or an issue comment; a day with neither means the run failed before
  step 3. Check the routine's run log.
- The STATUS changelog is the human-readable history. The agent appends one line per run.
- Weekly, the owner skims the register (`docs/README.md`) to make sure the agent is keeping it
  honest.

## Activation checklist (issue #24)

1. Authorise the cloud environment on `pastacoin/pastacoin` (GitHub app or deploy token).
2. Add `tools/agent/daily_prompt.md` with the prompt above and `MODE: dry-run`.
3. Create the routine (name `pasta-daily`, cron `0 12 * * *`, repo
   `https://github.com/pastacoin/pastacoin`, connector Google-Drive, tools Bash/Read/Write/
   Edit/Glob/Grep).
4. Run it once by hand; read the dry-run comment; fix the prompt until the plan is sensible.
5. Flip to `MODE: live`. Review the first three PRs closely before trusting the cadence.
6. Optional: attach Gmail for the daily summary; create a second routine on
   `pastacoin.github.io` for Phase 4 work.

## Open questions for the owner

- Email summaries, or is the PR enough?
- Should the agent be allowed to merge documentation-only PRs?
- Which phases should use the larger model?
