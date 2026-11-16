# Headless workflows

## Configuration

`SETOOLKIT_CODE_PATH` is the parent directory containing the user's repositories.
Expand `~`, resolve it, and verify that it exists. `SETOOLKIT_GITHUB_ACCESS_TOKEN`
is used by the toolkit's GitHub client; `gh` has its own authentication configuration.
Use `gh auth status` to check it. Do not print access tokens in reports or logs.

For a GitHub Enterprise host, verify the host and use the matching GitHub CLI
authentication context. Do not assume public GitHub credentials apply there.

## PR triage

These commands return JSON and do not wait for terminal input:

```sh
gh search prs --state open --review-requested @me --limit 100 --json number,title,url,repository,updatedAt
gh search prs --state open --author @me --limit 100 --json number,title,url,repository,updatedAt
gh pr view "$number" --repo "$owner_repo" --json number,url,reviewDecision,reviews,statusCheckRollup
```

Search results are bounded by the command's limit. Use an explicit `--limit`,
report it, and narrow searches to an owner/repository when appropriate. For a full
comment audit use `gh api --paginate` on issue comments and pull review comments.
Those endpoints include different kinds of comments; neither alone describes all
responses. Use the submitted review records when deciding whether someone replied.

## Stashes

```sh
git --no-pager -C "$repo" stash list --format='%gd%x09%H%x09%gs'
git --no-pager -C "$repo" stash show -p 'stash@{0}'
```

Inspecting a stash does not require applying it. If the user asks for an apply or
rename, re-read the stash reference and commit ID immediately before mutation:
stash indexes shift when another stash is created or removed. `stash pop` removes
the entry on successful application; `stash apply` retains it. Choose the behavior
the user requested and report conflicts without discarding working changes.

## Project paths and worktrees

Find `autoci.json` under the selected monorepo, excluding irrelevant generated
directories when possible, and return its parent. Quote paths and do not use a
shared `/tmp/qs` file in an agent. The shell's `,qs` function is for changing the
user's current interactive shell; a headless agent should use its tool's working
directory parameter instead.

Inspect existing worktrees before adding another:

```sh
git -C "$repo" worktree list --porcelain
git -C "$repo" worktree add "$destination" "$existing_branch"
```

The documented `,gcs` interface selects an existing branch. If the user requests
a new branch, Git supports `worktree add -b`; do not invent a toolkit `--create`
flag unless the installed version advertises it.

## S3 console URLs

Split an `s3://` URI into bucket and key. Use `urllib.parse.urlencode` for the
`region` and `prefix` query parameters, preserving spaces, `&`, `#`, `+`, Unicode,
and literal percent signs. Region selection should affect both the host and the
query. Conversion itself requires neither AWS credentials nor an S3 read.

## Database imports

Install the database package into an environment compatible with its metadata.
Use a caller-supplied encoding or the documented default. Check the source and
destination names, read successfully, then replace the destination atomically.
An invalid source should not delete the previous table. Do not assume that sorting
input fragments guarantees SQL result order; queries need `ORDER BY` for that.
