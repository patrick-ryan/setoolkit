# Overview
SE Toolkit is a collection of convenient tools for managing the soft ops side of software engineering:
- ticket management
- SDLC
- version control
- monorepo

The main product is a CLI (Mac & Linux compatible) that is available as a set of binaries that can be run at any time from your PATH.

# Installation

```shell
cd tools_cli

# <create & activate virtual environment for this>

# project build
pip install '.[build]'
. ./build.sh

# these update your current session for usage
. ./init.sh
export PATH=$PATH:$(pwd)/bin
```

The following environment variables may be needed depending on use case:
```shell
# for monorepo tools
SETOOLKIT_CODE_PATH

# for github access
SETOOLKIT_GITHUB_HOSTNAME  # (default: github.com)
SETOOLKIT_GITHUB_ACCESS_TOKEN

# for ,gpr
SETOOLKIT_GPR_SINCE  # (default: 4 weeks ago)
```
(Tip: if you have a .env file, you can export it with `export $(cat .env | xargs)`)

Update your RC file or whatever with the init invocation and path update, and your system setup should be complete.

# Usage

## GCS (WIP)

Manage git worktrees.

```
,gcs --branch-name <existing-branch>
```

## GPR

List out pull requests needing attention.

Shows pull requests in priority order: recent comments mentioning you, your open
pull requests, then recent pull requests you have not responded to. Comments and
submitted reviews both count as responses. Within each category, newest entries
appear first; each pull request appears only once in its highest-priority category.

`SETOOLKIT_GPR_SINCE` filters mention creation dates and unresponded pull request
creation dates. It defaults to four weeks ago; your own open pull requests are
included regardless of age. Use an ISO date such as `2026-10-01` for an override.
Mentioned comments may belong to resolved threads: the REST comment API does not
expose resolution status, so the category is labeled `MENTIONED`.

Runs a bit slowly right now, sorry.

```
,gpr
```

## GST

Manage your local git stashes.

Use Enter to inspect, `r` to rename, and `a` to pop the selected stash. Renaming
preserves its contents and moves it to the top of the stash list without changing
your working files. An empty stash list exits cleanly.

```
,gst
```

## QS

List other project directories using fuzzy search logic, and switch your current working directory to the selected project.

```
,qs <search_text>
```

Quote searches containing spaces. Canceling leaves your current directory
unchanged. The shell wrapper uses a private, per-invocation result file and removes
it on completion; source `tools_cli/init.sh` again after updating the binaries.

## RT

Switch working directory to the root of your current project.

```
,rt
```

## S3U2U

Convert an AWS S3 uri to the corresponding url.

```
,s3u2u <uri>
```

# Use as an agent skill

The repository includes an Agent Skills-format [SKILL.md](SKILL.md), with semantic
instructions for PR triage, stash inspection, project navigation, worktrees, S3
links, and repository contributions. It includes headless alternatives to the
interactive terminal commands.

To install manually, create a `setoolkit` directory in your agent client's skill
directory and copy `SKILL.md` plus the `references/` directory into it. Keep the
references alongside the manifest so its relative links resolve. This installs
instructions, not the CLI or Python dependencies; install those separately when
needed and identify the target repository explicitly.

Example requests: “Inspect my latest stash without applying it”, “Which PRs need
my attention?”, and “Split these SE Toolkit fixes into upstream pull requests”.
Reusable behavioral evaluation cases are in `evals/`.
