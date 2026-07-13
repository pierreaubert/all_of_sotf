---
name: sotf-workflow
description: "Use for SOTF repository planning and implementation workflow: TokenSave-first code research, issue creation before implementation plans, branch and PR hygiene, verification summaries, commit drafting, and avoiding user worktree churn."
---

# SOTF Workflow

## Core Flow

Use this skill whenever work is in `gpui-toolkit`, `math-audio`, `autoeq`, `sotf` or derived worktree and the task involves planning, implementing, reviewing, committing, or opening a PR.

1. Start code research with TokenSave tools before reading source files.
2. For each new implementation plan, create or identify the corresponding issue before coding.
3. Keep changes scoped to the requested behavior and existing ownership boundaries.
4. Verify with the narrowest meaningful commands first, then broader checks when blast radius requires them.
5. Summarize changed behavior, verification, and residual risk before commit or PR.
6. Push the branch and open a PR when the implementation plan is complete and the user has not asked to stop earlier.

## Research Order

- Use `tokensave_context` first for unfamiliar code areas.
- Use `tokensave_search` for known symbols, then callers/callees/impact tools if available.
- Use `rg` or file reads only after TokenSave gives the likely files or when searching raw text, config, docs, logs, or CLI strings.
- If TokenSave cannot answer a structural question, query `.tokensave/tokensave.db` directly before doing broad source scans.

## Worktree Care

- Assume unrelated uncommitted changes belong to the user.
- Do not revert, reset, or overwrite changes you did not make.
- Before touching files with existing modifications, inspect the diff and work with those edits.
- Prefer non-interactive git commands.

## References

- Read `references/repo-protocol.md` when creating an issue, branch, commit, or PR.
