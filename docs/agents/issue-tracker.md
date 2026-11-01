# Issue tracker: GitHub

Issues and specs live in GitHub Issues for `micknudsen/oncohawk`:
https://github.com/micknudsen/oncohawk/issues

When a skill says to publish to the issue tracker, create an issue in this repository. When it says to fetch a ticket, read the issue body, labels, and relevant comments here.

## Operations

- Prefer the connected GitHub tools where they support the operation. Otherwise use the authenticated `gh` CLI with an explicit `--repo micknudsen/oncohawk` target.
- Verify the repository target before the first issue creation in a session. File issues only in this project's repository.
- Supply Markdown bodies through structured tool arguments or `--body-file` with the CLI, preserving real newlines.
- Use the vocabulary in `docs/agents/triage-labels.md` when applying or removing triage labels.
- When closing an issue requires an explanation, post the authorized explanation before closing; do not assume a close operation adds a comment to an already-closed issue.

## Pull requests as a triage surface

**PRs as a request surface: no.**

## Authorization boundaries

Setup and explicitly requested spec/issue publication do not authorize pipeline implementation, software installation, GitHub protection changes, bootstrap commits, pushes, or merges. Preserve the project's protected-master, required-CI, squash-merge, and linear-history rules when implementation is separately authorized.
