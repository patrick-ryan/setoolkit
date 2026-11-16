---
tags: [skill-creator]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

I'm using SE Toolkit in a headless coding agent. Show me how to inspect the newest
stash in `/work/my project` and find the billing project in that monorepo without
changing any files. Return commands and explain how to use the selected path;
do not actually run them against a repository.
