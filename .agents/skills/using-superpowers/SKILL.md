---
name: using-superpowers
description: Guidance on superpowers skills. User-invoked.
disable-model-invocation: true
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, ignore this skill.
</SUBAGENT-STOP>

## Skill Usage Policy

Superpowers skills are **advisory and optional tools**. They are available to guide complex tasks, but they should **NOT** be automatically or forcibly invoked for every request.

## The Rule

- **Flexible & Discretionary**: Use skills when they genuinely add value or when explicitly requested by the user.
- **Direct Execution for Simple Tasks**: For straightforward questions, code tweaks, minor bug fixes, or direct instructions, proceed directly without triggering heavy skill workflows.
- **User Intent First**: Direct user instructions and repository rules in `AGENTS.md` take top priority over skill recommendations.

## Platform Adaptation

If your harness appears here, read its reference file for special instructions:

- Codex: `references/codex-tools.md`
- Pi: `references/pi-tools.md`
- Antigravity: `references/antigravity-tools.md`

## User Instructions

User instructions (CLAUDE.md, AGENTS.md, GEMINI.md, etc, direct requests) take precedence over skills, which in turn override default behavior. Only use skill workflows when helpful or when your human partner asks for them.

