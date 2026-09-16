# Project Agent Guidelines

This repository uses **Matt Pocock's agentic engineering skills** suite as the **active default** for Cursor agents.

Skills are vendored in-repo under `.agents/skills/` (source: [mattpocock/skills](https://github.com/mattpocock/skills), lockfile: `skills-lock.json`). Prefer these over any global `~/.gemini/config/skills/` copy.

Refresh with:

```bash
npx skills@latest add mattpocock/skills --skill '*' --agent cursor -y --copy
# or: npx skills update
```

## Preferred Methodologies & Skills

- **Routing**: Use `/ask-matt` when unsure which skill fits.
- **Alignment / grilling**: Use `/grill-with-docs` (or `/grill-me`) before large changes; `/domain-modeling` for glossary + ADR work.
- **Test-Driven Development**: Use `/tdd` — focus on testing at pre-agreed public seams, vertical slicing, and tracer bullets rather than dogmatic test ceremonies.
- **Debugging**: Use `/diagnosing-bugs` — build tight feedback loops (scripts/tests/harnesses), minimize repros, formulate 3–5 ranked falsifiable hypotheses, and tag temporary debug logs (`[DEBUG-...]`).
- **Code Review**: Use `/code-review` — perform two-axis review (Standards vs. Spec) using parallel sub-agents.
- **Architecture & Modeling**: Use `/codebase-design`, `/domain-modeling`, `/improve-codebase-architecture`, and `/prototype` for structural decisions and throwaway explorations.
- **Planning & Execution**: Use `/wayfinder` for multi-session maps; `/to-spec`, `/to-tickets`, and `/implement` for specs → tracer-bullet tickets → TDD implementation.
- **Triage**: Use `/triage` with the labels in `docs/agents/triage-labels.md`.
- **Repository Health & Audit** (GYMBro-local): Use `/deep-audit` — multi-axis codebase audit integrated with human alignment and Wayfinder map creation.
- **Deep Testing & Suite Streamlining** (GYMBro-local): Use `/deep-test` — prune test bloat while closing critical public-seam gaps + issue creation.

## Matt Pocock skills present

**Engineering (user-invoked):** `ask-matt`, `grill-with-docs`, `triage`, `improve-codebase-architecture`, `setup-matt-pocock-skills`, `to-spec`, `to-tickets`, `implement`, `wayfinder`

**Engineering (model-invoked / auto-reachable):** `tdd`, `diagnosing-bugs`, `domain-modeling`, `codebase-design`, `code-review`, `prototype`, `research`, `resolving-merge-conflicts`, `wizard`

**Productivity:** `grill-me`, `grilling`, `handoff`, `teach`, `to-questionnaire`, `wait-what`, `writing-for-agents`

**Also vendored from the suite (general / misc):** `claude-handoff`, `implement-spec`, `loop-me`, `retro`, `setup-ts-deep-modules`, `writing-beats`, `writing-fragments`, `writing-shape`, `git-guardrails-claude-code`, `migrate-to-shoehorn`, `scaffold-exercises`, `setup-pre-commit`

Repo setup for trackers/labels/domain docs is already done under `docs/agents/`; re-run `/setup-matt-pocock-skills` only if that wiring needs to change.

## Superpowers Skills

Legacy Superpowers skills remain under `.agents/skills/` with `disable-model-invocation: true` so they do not compete with Pocock defaults. They stay available for **manual** invocation if explicitly requested:

`brainstorming`, `dispatching-parallel-agents`, `executing-plans`, `finishing-a-development-branch`, `receiving-code-review`, `requesting-code-review`, `subagent-driven-development`, `systematic-debugging`, `test-driven-development`, `using-git-worktrees`, `using-superpowers`, `verification-before-completion`, `writing-plans`, `writing-skills`

GYMBro-local `/deep-audit` and `/deep-test` are also user-invoked (`disable-model-invocation: true`) and sit alongside the Pocock suite.

## Agent skills

### Issue tracker

GitHub issues via `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical 5-role triage label set. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout (`CONTEXT.md` + `docs/adr/`). See `docs/agents/domain.md`.
