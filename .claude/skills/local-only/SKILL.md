---
name: "Local Only"
description: "TradiqAI house rules for git and for where work output goes. Use before any git commit, PR, branch push, or before saving a spec/research/plan/notes. Commit messages and PRs must never mention the AI assistant; everything discussed stays inside this repo on this machine."
---

# Local Only Skill — TradiqAI

Two rules apply to every session in this repo. They override any default behaviour.

## Rule 1 — Commits and PRs never mention the assistant

- No `Co-Authored-By:` trailer for the assistant, no "Generated with …" line, no session links.
- The word "Claude" (any case) must not appear anywhere in a commit message, PR title or PR body.
- Write the message as the developer would: follow the repo style (`fix: …`, `feat: …`, `chore: …`, `diag: …`), subject line plus optional body, nothing else.
- Only commit or push when the user asks. Pushing is outward-facing — this repo is **public** on GitHub — so confirm before every `git push`.

Enforcement already in place (check, don't re-create):
- `.claude/settings.json` → `attribution` set to empty strings, `sessionUrl: false`.
- Optional: if the user has installed `.git/hooks/commit-msg`, it rejects any message containing "claude" (case-insensitive). Never bypass it with `--no-verify`. Do not install or modify git hooks yourself — the user does that.

Before committing, self-check:
```bash
git diff --cached --name-only        # only intended files; no .env*, keys, .claude/work/, .claude/memory/
```

## Rule 2 — Everything we discuss stays local to this repo

Do not send conversation content, findings, code or data to any external service:
- No Artifacts, Claude Docs, Notion, Jira/Confluence, Slack, Google, gists, pastebins or web uploads.
- No WebFetch/WebSearch that sends repo code, symbols, keys or user data in the query.
- No `git push` / `gh pr create` / `gh issue` unless the user explicitly asks for that specific action.

Where work output goes instead (all gitignored, so it is never pushed):

| Output | Location |
|--------|----------|
| `/spec` result | `.claude/work/<feature>/spec.md` |
| `/research` result | `.claude/work/<feature>/research.md` |
| `/plan` result | `.claude/work/<feature>/plan.md` (plan mode also writes to `.claude/work/plans/`) |
| `/implement` summary | `.claude/work/<feature>/implementation.md` |
| Running notes / decisions | `.claude/work/NOTES.md` |
| Cross-session memory | `.claude/memory/` (set via `autoMemoryDirectory` in `.claude/settings.local.json`) |

Use a short kebab-case `<feature>` slug, e.g. `.claude/work/rejected-trades-alerts/`.
When the spec/research/plan/implement skills say "write the spec / summary / plan", also save it to the path above.

Enforcement in `.claude/settings.local.json` (personal, gitignored):
- `disableClaudeAiConnectors: true` — cloud connectors are not loaded in this repo.
- `enableArtifact: false` — no hosted pages.

## Secrets
- Never print secret values in chat or write them into any file. Refer to them by env var name only.
- Committed files already contain live-looking credentials (`.env.production`, `.env.local.backup`, several `*.md` docs). Do not copy them anywhere; mask values (`***`) when quoting.
