"""Offline unittests for render.py. No network: every payload is built here or
produced by the vendored workspace_check.py over the fixture tree.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import render
import workspace_check

THIS_DIR = Path(__file__).resolve().parent
FIXTURE = THIS_DIR / "tests" / "fixtures" / "workspace"


def make_payload(score=8.1, band="disciplined", checks=None) -> dict:
    if checks is None:
        checks = [
            {
                "id": "claude-md-present",
                "status": "PASS",
                "evidence": "CLAUDE.md at the root, 0.1 KB",
                "pattern": "9-context-is-a-budget-not-a-constant",
            },
            {
                "id": "permissions-floor",
                "status": "WARN",
                "evidence": "no permissions block in settings",
                "pattern": "4-tier-by-mechanical-impact-not-by-tone",
            },
            {
                "id": "mcp-config",
                "status": "NA",
                "evidence": "no .mcp.json",
                "pattern": "6-credentials-live-in-one-place-never-in-files",
            },
        ]
    return {"score": score, "band": band, "checks": checks}


def run_main(payload, env=None) -> tuple[int, str, dict]:
    """Call main() in-process with runner files in a temp dir.

    Returns the exit code, stdout, and the text of each runner file.
    """
    with tempfile.TemporaryDirectory() as td:
        out_path = os.path.join(td, "output")
        summary_path = os.path.join(td, "summary")
        payload_path = os.path.join(td, "payload.json")
        text = payload if isinstance(payload, str) else json.dumps(payload)
        with open(payload_path, "w", encoding="utf-8") as handle:
            handle.write(text)
        full_env = {
            "GITHUB_OUTPUT": out_path,
            "GITHUB_STEP_SUMMARY": summary_path,
            "MIN_SCORE": "",
            "SUMMARY": "true",
        }
        full_env.update(env or {})
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = render.main([payload_path], full_env)
        files = {}
        for name, path in (("output", out_path), ("summary", summary_path)):
            files[name] = (
                Path(path).read_text(encoding="utf-8") if os.path.exists(path) else ""
            )
    return code, stdout.getvalue(), files


def parse_outputs(text: str) -> dict:
    """Read the name<<delimiter format back into a dict."""
    outputs, lines, i = {}, text.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        if "<<" in line:
            name, delimiter = line.split("<<", 1)
            value = []
            i += 1
            while lines[i] != delimiter:
                value.append(lines[i])
                i += 1
            outputs[name] = "\n".join(value)
        i += 1
    return outputs


# ---------------------------------------------------------------------------
# min-score gate
# ---------------------------------------------------------------------------


class GateTests(unittest.TestCase):
    def test_blank_min_score_never_fails(self):
        for raw in ("", "   ", None):
            with self.subTest(raw=raw):
                env = {} if raw is None else {"MIN_SCORE": raw}
                code, stdout, _ = run_main(make_payload(score=0.0, band="exposed"), env)
                self.assertEqual(code, 0)
                self.assertNotIn("::error::", stdout)

    def test_score_below_threshold_exits_1_with_one_line_reason(self):
        code, stdout, _ = run_main(make_payload(score=6.5), {"MIN_SCORE": "7"})
        self.assertEqual(code, 1)
        errors = [ln for ln in stdout.splitlines() if ln.startswith("::error::")]
        self.assertEqual(
            errors, ["::error::Workspace score 6.5/10 is below min-score 7."]
        )

    def test_score_at_threshold_passes(self):
        for score, raw in ((7.0, "7"), (8.1, "8.1"), (10.0, "10")):
            with self.subTest(score=score, raw=raw):
                code, stdout, _ = run_main(
                    make_payload(score=score), {"MIN_SCORE": raw}
                )
                self.assertEqual(code, 0)
                self.assertNotIn("::error::", stdout)

    def test_score_above_threshold_passes(self):
        code, _, _ = run_main(make_payload(score=9.4), {"MIN_SCORE": " 9 "})
        self.assertEqual(code, 0)

    def test_non_numeric_threshold_exits_2_with_clear_message(self):
        for raw in ("seven", "7/10", "nan", "inf", "8,5"):
            with self.subTest(raw=raw):
                code, stdout, files = run_main(make_payload(), {"MIN_SCORE": raw})
                self.assertEqual(code, 2)
                self.assertIn("::error::min-score must be", stdout)
                # A configuration error writes nothing to the runner files.
                self.assertEqual(files["output"], "")

    def test_non_numeric_threshold_cannot_inject_a_workflow_command(self):
        code, stdout, _ = run_main(
            make_payload(), {"MIN_SCORE": "x\n::warning::injected"}
        )
        self.assertEqual(code, 2)
        self.assertFalse(
            any(ln.startswith("::warning::") for ln in stdout.splitlines())
        )

    def test_failing_gate_still_writes_outputs_and_summary(self):
        code, _, files = run_main(
            make_payload(score=4.0, band="exposed"), {"MIN_SCORE": "5"}
        )
        self.assertEqual(code, 1)
        self.assertEqual(parse_outputs(files["output"])["score"], "4.0")
        self.assertIn("Minimum score 5: not met.", files["summary"])

    def test_bad_summary_flag_exits_2(self):
        code, stdout, _ = run_main(make_payload(), {"SUMMARY": "yes"})
        self.assertEqual(code, 2)
        self.assertIn("::error::summary must be", stdout)

    def test_malformed_payload_exits_2(self):
        for text in ("", "not json", "[]", '{"band": "x", "checks": []}'):
            with self.subTest(text=text):
                code, stdout, _ = run_main(text)
                self.assertEqual(code, 2)
                self.assertIn("::error::", stdout)


# ---------------------------------------------------------------------------
# Badge
# ---------------------------------------------------------------------------


class BadgeTests(unittest.TestCase):
    def test_band_to_color_map(self):
        self.assertEqual(render.band_color("disciplined"), "brightgreen")
        self.assertEqual(render.band_color("maturing"), "yellow")
        self.assertEqual(render.band_color("exposed"), "red")
        self.assertEqual(render.band_color("unheard-of"), "lightgrey")

    def test_color_map_covers_every_band_the_linter_returns(self):
        bands = {
            workspace_check.score_checks(checks)[1]
            for checks in (
                [workspace_check.Check("a", "PASS", "", 9)],
                [
                    workspace_check.Check("a", "PASS", "", 9),
                    workspace_check.Check("b", "FAIL", "", 9),
                ],
                [workspace_check.Check("a", "FAIL", "", 9)],
            )
        }
        self.assertEqual(bands, set(render.BAND_COLORS))

    def test_badge_url_is_encoded(self):
        self.assertEqual(
            render.badge_url(7.5, "maturing"),
            "https://img.shields.io/badge/workspace%20score-7.5%2F10-yellow",
        )

    def test_whole_score_keeps_one_decimal(self):
        self.assertEqual(
            render.badge_url(10.0, "disciplined"),
            "https://img.shields.io/badge/workspace%20score-10.0%2F10-brightgreen",
        )

    def test_shields_escape_doubles_dash_and_underscore(self):
        self.assertEqual(render.shields_escape("a-b_c d/e"), "a--b__c%20d%2Fe")

    def test_badge_markdown(self):
        self.assertEqual(
            render.badge_markdown(8.1, "disciplined"),
            "[![workspace score](https://img.shields.io/badge/workspace%20score-"
            "8.1%2F10-brightgreen)](https://github.com/jimy-r/"
            "agent-workspace-architecture#try-it-in-60-seconds)",
        )

    def test_outputs_carry_score_band_and_badge(self):
        code, _, files = run_main(make_payload(score=8.1, band="disciplined"))
        self.assertEqual(code, 0)
        outputs = parse_outputs(files["output"])
        self.assertEqual(
            outputs,
            {
                "score": "8.1",
                "band": "disciplined",
                "badge-markdown": render.badge_markdown(8.1, "disciplined"),
            },
        )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class SummaryTests(unittest.TestCase):
    def test_summary_with_not_applicable_checks(self):
        _, _, files = run_main(make_payload())
        summary = files["summary"]
        self.assertIn(
            "**Score 8.1/10, disciplined** (2 scored, 1 not applicable)", summary
        )
        self.assertIn("| N/A | mcp-config | no .mcp.json |", summary)
        self.assertIn("| WARN | permissions-floor |", summary)
        self.assertIn(
            "[4-tier-by-mechanical-impact-not-by-tone]("
            + workspace_check.PATTERNS_URL
            + "#4-tier-by-mechanical-impact-not-by-tone)",
            summary,
        )
        self.assertIn(
            "```markdown\n" + render.badge_markdown(8.1, "disciplined") + "\n```",
            summary,
        )
        self.assertNotIn("Minimum score", summary)

    def test_summary_with_every_check_not_applicable(self):
        checks = [
            {
                "id": "mcp-config",
                "status": "NA",
                "evidence": "no .mcp.json",
                "pattern": "6-x",
            }
        ]
        _, _, files = run_main(make_payload(score=0.0, band="exposed", checks=checks))
        self.assertIn("(0 scored, 1 not applicable)", files["summary"])

    def test_summary_without_not_applicable_checks_has_no_tail(self):
        checks = [{"id": "a", "status": "PASS", "evidence": "ok", "pattern": "9-x"}]
        _, _, files = run_main(make_payload(score=10.0, checks=checks))
        self.assertIn("(1 scored)", files["summary"])
        self.assertNotIn("not applicable", files["summary"])

    def test_summary_off_writes_no_summary_but_still_writes_outputs(self):
        for raw in ("false", "FALSE", " false "):
            with self.subTest(raw=raw):
                _, _, files = run_main(make_payload(), {"SUMMARY": raw})
                self.assertEqual(files["summary"], "")
                self.assertIn("badge-markdown", files["output"])

    def test_threshold_line_when_met(self):
        _, _, files = run_main(make_payload(score=8.1), {"MIN_SCORE": "8"})
        self.assertIn("Minimum score 8: met.", files["summary"])

    def test_evidence_from_the_scanned_tree_is_escaped(self):
        checks = [
            {
                "id": "secrets-in-files",
                "status": "FAIL",
                "evidence": "1 hit(s): a|b.md <img src=x>\nnext `cmd`",
                "pattern": "6-credentials-live-in-one-place-never-in-files",
            }
        ]
        _, _, files = run_main(make_payload(score=0.0, band="exposed", checks=checks))
        row = next(
            ln for ln in files["summary"].splitlines() if "secrets-in-files" in ln
        )
        self.assertIn("a\\|b.md &lt;img src=x&gt; next \\`cmd\\`", row)
        self.assertNotIn("<img", files["summary"])

    def test_pattern_that_is_not_a_slug_is_not_linked(self):
        checks = [
            {
                "id": "a",
                "status": "PASS",
                "evidence": "ok",
                "pattern": "x)(javascript:1",
            }
        ]
        _, _, files = run_main(make_payload(checks=checks))
        self.assertNotIn("](" + workspace_check.PATTERNS_URL + "#x", files["summary"])


# ---------------------------------------------------------------------------
# End to end over the fixture tree
# ---------------------------------------------------------------------------


class FixtureTests(unittest.TestCase):
    def linter_json(self) -> str:
        proc = subprocess.run(
            [
                sys.executable,
                str(THIS_DIR / "workspace_check.py"),
                "--json",
                str(FIXTURE),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout

    def test_fixture_scores_as_ci_expects(self):
        code, _, files = run_main(self.linter_json(), {"MIN_SCORE": "8"})
        self.assertEqual(code, 0)
        outputs = parse_outputs(files["output"])
        self.assertEqual(outputs["score"], "8.1")
        self.assertEqual(outputs["band"], "disciplined")
        self.assertIn("(8 scored, 4 not applicable)", files["summary"])

    def test_stdin_payload(self):
        with tempfile.TemporaryDirectory() as td:
            out_path = os.path.join(td, "output")
            env = {"GITHUB_OUTPUT": out_path, "SUMMARY": "false"}
            with mock.patch("sys.stdin", io.StringIO(self.linter_json())):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = render.main([], env)
            self.assertEqual(code, 0)
            self.assertEqual(
                parse_outputs(Path(out_path).read_text(encoding="utf-8"))["score"],
                "8.1",
            )


if __name__ == "__main__":
    unittest.main()
