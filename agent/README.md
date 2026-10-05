# Rigatoni — the PaSta project agent

Everything that makes the project's agent who it is lives in this folder, in the open. Anyone
can read it, propose changes by pull request, or run their own copy.

| File | What it is |
|---|---|
| `IDENTITY.md` | Name, role, voice, and what Rigatoni is and is not. |
| `GUARDRAILS.md` | What it may do, what it must never do, and whose instructions it follows. |
| `ACCOUNTS.md` | Every account held in Rigatoni's name: service, purpose, who can recover it. |
| `DECISIONS.md` | Running log of decisions Rigatoni made or was given, newest first. |

How it runs (schedule, daily prompt, kill switch) is designed in `docs/AGENT.md`.

## What is not here

Credentials. Passwords, tokens, SSH keys and API keys are never committed, to this repository
or any other. They live in the secret store of whatever runs the agent and in the owner's
password manager. `ACCOUNTS.md` records that a credential exists and where it is kept, never
its value.

## Running your own copy

The identity, guard rails and memory are plain files. Point any capable model at this folder
and the documents listed in `docs/README.md`, give it your own credentials for your own fork,
and it is the same agent in every respect that is written down. The model behind the project's
own instance is a commercial one (see `IDENTITY.md`); that part is a dependency, not something
this repository can open.
