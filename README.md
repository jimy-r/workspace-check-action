# workspace-check-action

A composite GitHub Action that runs the [workspace check](https://github.com/jimy-r/agent-workspace-architecture#try-it-in-60-seconds) from agent-workspace-architecture in CI. The check is a single-file, read-only linter that scores an agent workspace out of 10 against the patterns a script can verify. This action puts the score, its band and a README badge on every run.

[![workspace score](https://img.shields.io/badge/workspace%20score-8.1%2F10-brightgreen)](https://github.com/jimy-r/agent-workspace-architecture#try-it-in-60-seconds)

That badge is this repo's test fixture. Your own run prints yours in the job summary.

## What it checks

Twelve checks, each tied to a numbered pattern in [PATTERNS.md](https://github.com/jimy-r/agent-workspace-architecture/blob/main/PATTERNS.md). They cover the size of the always-loaded instruction files, settings and hook shape, the permission floor, credentials sitting in files, skill and agent frontmatter, blocks duplicated across instruction files, and the size of the memory index. Each prints one evidence line. A high score means the floor is in place. It says nothing about whether the workspace does good work.

The linter runs no model and makes no network call. It writes nothing to the tree and never executes a file it finds there. A PASS earns a full point, a WARN half a point and a FAIL none, and a check that doesn't apply (N/A) drops out of the score. The score is the share of points earned, out of 10.

## Quickstart

```yaml
name: Workspace check
on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  workspace-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - uses: jimy-r/workspace-check-action@v1
```

There's no setup step. GitHub-hosted runners ship Python 3.9 or later, both scripts use the standard library only, and the action runs on Linux, macOS and Windows runners.

`@v1` moves to each new `v1.x.y` release. Pin a release tag or a commit SHA if you'd rather take updates on your own schedule.

### Fail below a score

```yaml
      - uses: jimy-r/workspace-check-action@v1
        with:
          path: .
          min-score: '8'
```

Leave `min-score` blank and the step reports without failing. With a number set, a score below it fails the step with a one-line reason, after the outputs and the summary are written. A value that isn't a number fails with exit 2 and writes nothing. A good first rollout is report-only, then a threshold at the score you have today, so a change that lowers it shows up in review.

### Use the outputs

```yaml
      - id: workspace
        uses: jimy-r/workspace-check-action@v1

      - name: Print the score
        shell: bash
        env:
          SCORE: ${{ steps.workspace.outputs.score }}
          BAND: ${{ steps.workspace.outputs.band }}
        run: echo "Workspace score $SCORE/10 ($BAND)"
```

Pass outputs to later steps through `env:`, as above, rather than writing the expression into a `run:` body.

## Inputs

| Input | Default | Description |
|---|---|---|
| `path` | `.` | Directory to check, relative to the checkout. |
| `min-score` | `''` | Fail the step when the score is below this number, out of 10. Blank never fails. A value that is not a number fails with exit 2. |
| `summary` | `'true'` | `'true'` writes the score, the check table and the badge snippet to the job summary. `'false'` writes none of it. Outputs are set either way. |

## Outputs

| Output | Example | Description |
|---|---|---|
| `score` | `8.1` | The score out of 10, to one decimal place. |
| `band` | `disciplined` | The linter's band: `disciplined`, `maturing` or `exposed`. |
| `badge-markdown` | see below | A shields.io badge in markdown, ready to paste into a README. |

## The badge

```markdown
[![workspace score](https://img.shields.io/badge/workspace%20score-8.1%2F10-brightgreen)](https://github.com/jimy-r/agent-workspace-architecture#try-it-in-60-seconds)
```

| Band | Score | Badge colour |
|---|---|---|
| `disciplined` | 8 and up | `brightgreen` |
| `maturing` | 5 to under 8 | `yellow` |
| `exposed` | under 5 | `red` |

The badge is a static snapshot, copied from the summary or the `badge-markdown` output. It doesn't update itself, so paste it again when the score moves.

## The job summary

The summary opens with the score line and the count of scored and not-applicable checks. Then comes one row per check (status, id, evidence and a link to its pattern), then the badge snippet. Evidence text from the scanned tree is escaped before it's rendered, so a file in the repo can't inject markdown or HTML into the page.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | The check ran. Either no `min-score` was set, or the score met it. |
| `1` | The score is below `min-score`. Outputs and summary are still written. |
| `2` | The action could not use an input: a non-numeric `min-score`, a `summary` other than `'true'` or `'false'`, or a `path` that is not a directory. |

## Where the linter comes from

`workspace_check.py` is copied verbatim from [`tools/workspace_check.py`](https://github.com/jimy-r/agent-workspace-architecture/blob/main/tools/workspace_check.py) in agent-workspace-architecture. The commit it came from is in [`UPSTREAM`](UPSTREAM), and CI fails if the copy drifts from that commit. The same file runs locally with `python3 workspace_check.py <path>`.

## Security

Every input reaches the scripts through `env:`, and CI fails if an input expression appears in a `run:` body. The linter only reads the tree. It never executes or uploads anything it finds. Report a vulnerability through a private advisory, as [SECURITY.md](SECURITY.md) describes.

## License

MIT. See [LICENSE](LICENSE).

Built by James Ross, who maintains [agent-workspace-architecture](https://github.com/jimy-r/agent-workspace-architecture).
