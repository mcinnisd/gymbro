# Project Agent Guidelines

This repository uses **Matt Pocock's agentic engineering skills** suite (`~/.gemini/config/skills/`).

## Preferred Methodologies & Skills

- **Test-Driven Development**: Use `/tdd` — focus on testing at pre-agreed public seams, vertical slicing, and tracer bullets rather than dogmatic test ceremonies.
- **Debugging**: Use `/diagnosing-bugs` — build tight feedback loops (scripts/tests/harnesses), minimize repros, formulate 3–5 ranked falsifiable hypotheses, and tag temporary debug logs (`[DEBUG-...]`).
- **Code Review**: Use `/code-review` — perform two-axis review (Standards vs. Spec) using parallel sub-agents.
- **Architecture & Modeling**: Use `/codebase-design`, `/domain-modeling`, and `/prototype` for structural decisions and throwaway explorations.
- **Repository Health & Audit**: Use `/deep-audit` — multi-axis codebase audit (deduplication, streamlining, domain alignment) integrated with human alignment and Wayfinder map creation.
- **Deep Testing & Flow Verification**: Use `/deep-test` — test suite meta-audit (pruning shallow tests, public seam rigor) + dynamic suite execution + automated issue creation.
- **Planning & Execution**: Use native planning mode and `/implement`, `/to-tickets`, `/to-spec`.

## Superpowers Skills

All legacy Superpowers skills in `.agents/skills/` have model auto-invocation disabled (`disable-model-invocation: true`) to prevent intrusive ceremonies and redundant skill conflicts. They remain available for manual invocation if explicitly requested.

## Agent skills

### Issue tracker

GitHub issues via `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical 5-role triage label set. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout (`CONTEXT.md` + `docs/adr/`). See `docs/agents/domain.md`.

