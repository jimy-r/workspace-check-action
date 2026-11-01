# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.0] - 2026-11-01

### Added

- The job summary ends with two links: one to ask for a public second read of the workspace, one to post a score in Show and tell. The README has the same two links, and it now names redaction-check-action.
- The vendored linter scores a workspace that has an `AGENTS.md` and no `CLAUDE.md`.

### Changed

- Scores can move. A workspace with one instruction file now reads `duplicate-blocks` as not applicable instead of a pass, so it can score a little lower. This repo's test fixture went from 8.1 `disciplined` to 7.9 `maturing`, and a `min-score` set close to your old score may now fail.
- The check id `claude-md-present` is now `instruction-file-present`.

## [1.0.0] - 2026-10-30

### Added

- A composite action that runs the flagship's read-only workspace linter, `workspace_check.py`, over a directory in the checkout and reports the score out of 10 and its band.
- Inputs `path` (default `.`), `min-score` (default blank, which never fails) and `summary` (default `'true'`). Every input reaches the scripts through `env:`, never through an expression in a `run:` body.
- Outputs `score`, `band` and `badge-markdown`.
- A job summary with the score line, a table of every check (status, id, evidence and a link to its pattern in `PATTERNS.md`) and a shields.io badge snippet ready to paste.
- The `min-score` gate. A score below the threshold exits 1 with a one-line reason, after the outputs and summary are written. A threshold that is not a number exits 2 and writes nothing.
- `workspace_check.py` vendored verbatim, with the source commit in `UPSTREAM`. CI fails if the file drifts from the flagship at that commit.
