# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.0] - 2026-11-01

Scores move in this release, and `@v1` picks it up on its own. If you set `min-score`, read Changed first.

### Added

- The job summary ends with two links: one to ask for a public second read of the workspace, one to post a score in Show and tell. The README has the same two links, and it now names redaction-check-action.

### Fixed

Both fixes arrive with the vendored linter, now at flagship commit `bfd85fa`.

- A workspace whose only instruction file is `AGENTS.md` no longer fails the presence check. `CLAUDE.md`, `AGENTS.md` and their copies under `.claude/` all count. A workspace with none of them still fails.
- A check with nothing to read no longer passes. `context-budget`, `duplicate-blocks` and `secrets-in-files` report not applicable when they found nothing to scan, and a check that doesn't apply drops out of the score. `duplicate-blocks` also reads not applicable with one instruction file, because there's nothing to compare it with.

### Changed

- Scores move in both directions. `AGENTS.md` is now read, so a paragraph it shares with `CLAUDE.md` counts as a duplicate. This repo's test fixture is the `CLAUDE.md` and `MEMORY.md` row.

  | Workspace | 1.0.0 | 1.1.0 |
  |---|---|---|
  | Empty directory | 6.4 `maturing` | 3.8 `exposed` |
  | `CLAUDE.md` alone | 7.9 `maturing` | 7.5 `maturing` |
  | `AGENTS.md` alone | 6.4 `maturing` | 7.5 `maturing` |
  | `CLAUDE.md` and `MEMORY.md` | 8.1 `disciplined` | 7.9 `maturing` |
  | `CLAUDE.md` and `AGENTS.md` sharing a paragraph of 240 characters or more | 7.9 `maturing` | 7.1 `maturing` |

- A `min-score` near an old number can start failing. `min-score: '8'` on a `CLAUDE.md` and `MEMORY.md` workspace passed on 1.0.0 and fails on 1.1.0. Run once with `min-score` blank and set the threshold from the new score, or pin `@v1.0.0` until you've done that.
- The check id `claude-md-present` is now `instruction-file-present`. Anything keyed on the old id in `--json` output needs the new name. The Action's outputs (`score`, `band`, `badge-markdown`) keep their names.

## [1.0.0] - 2026-10-30

### Added

- A composite action that runs the flagship's read-only workspace linter, `workspace_check.py`, over a directory in the checkout and reports the score out of 10 and its band.
- Inputs `path` (default `.`), `min-score` (default blank, which never fails) and `summary` (default `'true'`). Every input reaches the scripts through `env:`, never through an expression in a `run:` body.
- Outputs `score`, `band` and `badge-markdown`.
- A job summary with the score line, a table of every check (status, id, evidence and a link to its pattern in `PATTERNS.md`) and a shields.io badge snippet ready to paste.
- The `min-score` gate. A score below the threshold exits 1 with a one-line reason, after the outputs and summary are written. A threshold that is not a number exits 2 and writes nothing.
- `workspace_check.py` vendored verbatim, with the source commit in `UPSTREAM`. CI fails if the file drifts from the flagship at that commit.
