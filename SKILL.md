---
name: setoolkit
description: >-
  Use SE Toolkit for engineering workflow requests: triage pull requests needing
  attention, inspect Git stashes, navigate monorepo projects, manage worktrees,
  convert S3 URIs, or adapt this repository's CLI and database helpers. Use this
  skill when users ask for these operations in SE Toolkit, including natural
  language requests that do not name a comma-prefixed command. Also use it when
  splitting SE Toolkit fixes into focused fork-to-upstream pull requests.
compatibility: Git and a shell; Python and package dependencies for toolkit code; authenticated GitHub CLI for GitHub operations.
---

# SE Toolkit

Translate the user's goal into the smallest useful workflow. This skill describes
how to use and extend the repository; loading it does not install its dependencies
or register executable tools.

## Establish context

1. Locate the user's target repository separately from the SE Toolkit checkout.
   A copied skill folder may contain only these instructions and references.
2. Read `git status --short --branch` before changing a repository. Preserve existing
   work and any worktrees you did not create.
3. Check whether a terminal is interactive. The toolkit's `,gst`, `,gpr`, and `,qs`
   interfaces wait for keystrokes; use the headless alternatives below in agents,
   CI, or piped sessions.
4. Read the installed command's help and repository metadata before relying on
   flags or Python versions. The toolkit may be installed from an older revision.

## Map intent to operations

| User intent | Interactive toolkit | Headless approach |
| --- | --- | --- |
| “Which PRs need my attention?” | `,gpr` | Query GitHub with `gh search prs`, then inspect individual PRs and reviews |
| “Show the stash from yesterday” | `,gst` | `git -C "$repo" stash list` and `git -C "$repo" stash show -p "$ref"` |
| “Find the billing project” | `,qs billing` | Find `autoci.json` files and return matching parent directories |
| “Take me to the project root” | `,rt` | Resolve the configured project directory and report its path |
| “Check out another branch alongside this one” | `,gcs --branch-name existing-branch` | Use `git worktree list --porcelain`, then an explicit worktree operation |
| “Open this S3 object in the console” | `,s3u2u "$uri"` | Encode the S3 key as a URL query parameter; no AWS request is needed |
| “Fix this loader / extend this command” | Repository source | Follow the change workflow below |

Read [headless workflows](references/headless-workflows.md) for executable
examples, configuration, and the difference between shell navigation and agent
working directories.

## Interpret PR attention accurately

Keep mentions, authored PRs, and outstanding review requests distinct. A submitted
approval, comment-only review, or changes-requested review is a response even if
it has no inline comments. Pending draft reviews are not submitted responses.
GitHub REST comments do not establish whether a review thread is resolved. Use
GraphQL `reviewThreads.isResolved` if resolution is required, or label the result
as a mention rather than claiming it is unresolved.

Preserve the requested priority while deduplicating by repository and PR number.
Include links and say what date field a lookback filters. Report a rate-limit or
access error as incomplete results rather than “no PRs need attention.”

## Adapt the repository

- Start with `tools_cli/src/` for CLI behavior, `tools_cli/init.sh` for parent-shell
  navigation, and `db_lib/db.py` for database imports. Read each package's
  `pyproject.toml` for its actual dependency and Python requirements.
- Keep business logic callable without a terminal, and keep display markup out of
  new machine-readable results. Prefer a small typed result over parsing Rich
  table output.
- Add regression tests for observable failures: preserved data after failed imports,
  cancellation exit codes, empty selections, special-character paths, and Git
  state before/after mutations. Use temporary repositories and mock external APIs.
- Run `python scripts/run_tests.py` if available. Otherwise discover the relevant
  package's tests with `python -m unittest discover -s <package>/tests -v` after
  installing that package's test dependencies. Missing tests are a gap, not a pass.
- Read [contribution workflow](references/contribution-workflow.md) when preparing
  commits, fork PRs, related PRs, or issues.

## Return useful results

For inspection, report what was found, relevant paths or URLs, and any limits on
the result. For changes, list the commits/PRs, actual checks run, and remaining
issues. A subprocess cannot change the user's parent-shell directory: return the
resolved path or explain which sourced shell function performs the change.
