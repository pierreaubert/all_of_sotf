# SOTF Repo Protocol

## Issue, Branch, PR

- New implementation plan: create an issue first unless the user explicitly asks for a local-only experiment.
- Use short branch names that include issue context when available, such as `fix/issue-177-roomeq-linux-export`.
- When done, push the branch and open a PR.
- PR descriptions should include:
  - `Closes #N` when applicable.
  - Summary bullets of behavior changes.
  - Verification commands and whether they passed.
  - Any known residual risk.

## Useful Tools

- `tea issues create --remote gitea ...`
- `tea pulls create --remote gitea --base master --head <branch> ...`
- `tea pulls edit <id> --remote gitea --description ...`
- `tokensave_commit_context` for commit messages.
- `tokensave_pr_context` for PR descriptions.

## Verification Ladder

Pick the smallest useful check for the edited area, then widen if the change affects shared contracts.

- General Rust formatting: `cargo fmt --all`.
- Workspace sanity: `just check` or targeted `cargo check -p <crate>`.
- Targeted tests: `cargo test -p <crate> <filter>`.
- Broad tests: `just ntest`.
- QA matrix: see `$sotf-release-qa` for release and slow QA selection.

## Commit Style

- Use imperative, specific commit subjects.
- Mention the user-visible or correctness effect, not only the edited file.
- Keep unrelated changes out of the commit.
