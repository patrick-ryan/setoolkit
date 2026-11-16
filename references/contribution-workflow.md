# Focused changes and pull requests

1. Inspect the worktree, remotes, and existing PRs before editing. Treat unrelated
   modifications as existing user work.
2. Group fixes by behavior and reviewer concern. Keep a bug fix with the regression
   test that demonstrates it. A license choice or a new product feature can be an
   issue with acceptance criteria rather than an incidental cleanup.
3. Add follow-up commits to an existing PR when they belong to the same concern.
   Create separate branches for independent changes. Avoid formatting unrelated
   files in a bug-fix PR.
4. With upstream read-only access, push to a fork and explicitly set the upstream
   target and base. For example, after resolving the actual repository and user:

   ```sh
   git push -u fork fix/topic
   gh pr create --repo "$upstream" --base main --head "$fork_owner:fix/topic" \
     --title "$title" --body-file "$body_file"
   ```

5. Link related PRs and describe genuine dependencies. Use GitHub CLI for independent
   fork-to-upstream PRs. For a repository with native stacked-PR support and actual
   dependent layers, `gh stack` can maintain the chain; inspect `gh stack view
   --json` and use non-interactive flags. Cross-fork branches are not automatically
   valid upstream base branches. If every PR must target upstream `main`, keep
   independent diffs and record any required merge order explicitly.
6. Validate combinations in a disposable worktree or with `git merge-tree
   --write-tree`. An unfinished merge error does not establish a content conflict.
   Preserve the user's checkout and leave unowned worktrees alone.
7. Record exact test commands, API mocks, supported runtime checks, and any skipped
   integrations in the PR body. Opening a PR is distinct from merging it; follow
   the user's requested operation and the upstream review process.

## Completion report

List updated PR URLs, new PR URLs, issues that require decisions, test results,
and any remaining merge dependencies. Report CI's observed state: a workflow file
existing in a fork does not establish that an upstream Actions run has passed.
