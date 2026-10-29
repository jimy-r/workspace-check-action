# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [1.0.0] - Unreleased

### Added

- A composite action that runs the flagship's read-only workspace linter, `workspace_check.py`, over a directory in the checkout and reports the score out of 10 and its band.
- Inputs `path` (default `.`), `min-score` (default blank, which never fails) and `summary` (default `'true'`). Every input reaches the scripts through `env:`, never through an expression in a `run:` body.
- Outputs `score`, `band` and `badge-markdown`.
- A job summary with the score line, a table of every check (status, id, evidence and a link to its pattern in `PATTERNS.md`) and a shields.io badge snippet ready to paste.
- The `min-score` gate. A score below the threshold exits 1 with a one-line reason, after the outputs and summary are written. A threshold that is not a number exits 2 and writes nothing.
- `workspace_check.py` vendored verbatim, with the source commit in `UPSTREAM`. CI fails if the file drifts from the flagship at that commit.
