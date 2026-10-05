# Account register

Every account held in Rigatoni's name or used by it. Values of credentials are never written
here; "kept in" says where the secret lives. The account holder of record is always a person.

| Service | Identifier | Purpose | Holder of record | Credential kept in | Status |
|---|---|---|---|---|---|
| Domain `pastacoin.org` | registrar account | The project's domain; DNS for the site and mail | Project owner | Owner's password manager | Active. Rigatoni has no access. |
| Email (Fastmail, custom domain) | `rigatoni@pastacoin.org` | Project role address for sign-ups and correspondence | Project owner | Owner's password manager | Active since 2026-10-03; sending and receiving verified. Rigatoni has no access yet (no app password issued). |
| GitHub | organisation `pastacoin` | Source, issues, pull requests, site | Project owner | Fine-grained token in the owner's local agent settings | Active (token scoped to this organisation's two repositories). |
| Seed node host (Hetzner Cloud, Helsinki) | `seed.pastacoin.org` | Public node other nodes sync from; built from `deploy/` in this repository | Project owner | SSH deploy key on the owner's machine (key-only login; no password login) | Live since 2026-10-05 (UTC) at `https://seed.pastacoin.org`. The genesis coins are held by a wallet the owner keeps; its key is not on the server. |

When an account is added, changed or closed, update this table in the same pull request.
