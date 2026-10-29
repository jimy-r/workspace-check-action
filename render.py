#!/usr/bin/env python3
"""render.py: turn workspace_check.py's JSON into action outputs and a summary.

Reads the linter's --json payload from a file argument or stdin. Writes the
score, band and badge-markdown outputs to $GITHUB_OUTPUT, writes a markdown
job summary to $GITHUB_STEP_SUMMARY when SUMMARY is 'true', then applies the
MIN_SCORE gate.

Environment:
    MIN_SCORE            blank never fails; a number fails a lower score
    SUMMARY              'true' or 'false'
    GITHUB_OUTPUT        set by the runner; skipped when unset
    GITHUB_STEP_SUMMARY  set by the runner; skipped when unset

Exit codes: 0 pass, 1 score below MIN_SCORE, 2 bad input (a MIN_SCORE or
SUMMARY it cannot read, or a payload that is not the linter's JSON).

Usage:
    python workspace_check.py --json <path> | python render.py
    python render.py payload.json

Stdlib only, Python 3.9+.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import uuid
from urllib.parse import quote

from workspace_check import PATTERNS_URL

BADGE_LABEL = "workspace score"
BADGE_LINK = (
    "https://github.com/jimy-r/agent-workspace-architecture#try-it-in-60-seconds"
)
BAND_COLORS = {
    "disciplined": "brightgreen",
    "maturing": "yellow",
    "exposed": "red",
}
UNKNOWN_BAND_COLOR = "lightgrey"
SLUG_RE = re.compile(r"^[a-z0-9-]+$")


class InputError(Exception):
    """A value the action was given that it cannot use. Exits 2."""


# --- Badge -------------------------------------------------------------------
def band_color(band: str) -> str:
    return BAND_COLORS.get(band, UNKNOWN_BAND_COLOR)


def shields_escape(text: str) -> str:
    # Shields.io static badges split the path on single dashes and read single
    # underscores as spaces, so both are doubled before percent-encoding.
    text = text.replace("-", "--").replace("_", "__")
    return quote(text, safe="")


def format_score(score: float) -> str:
    return f"{score:.1f}"


def badge_url(score: float, band: str) -> str:
    label = shields_escape(BADGE_LABEL)
    message = shields_escape(f"{format_score(score)}/10")
    return f"https://img.shields.io/badge/{label}-{message}-{band_color(band)}"


def badge_markdown(score: float, band: str) -> str:
    return f"[![{BADGE_LABEL}]({badge_url(score, band)})]({BADGE_LINK})"


# --- Gate --------------------------------------------------------------------
def parse_threshold(raw: str | None) -> float | None:
    """Blank means no gate. Anything else must be a finite number."""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        raise InputError(
            f"min-score must be blank or a number such as 7 or 7.5, got '{escape_command(text)}'."
        ) from None
    if not math.isfinite(value):
        raise InputError(
            f"min-score must be a finite number, got '{escape_command(text)}'."
        )
    return value


def gate(score: float, threshold: float | None) -> tuple[int, str]:
    if threshold is None:
        return 0, ""
    if score < threshold:
        return 1, (
            f"Workspace score {format_score(score)}/10 is below min-score "
            f"{threshold:g}."
        )
    return 0, ""


def parse_summary_flag(raw: str | None) -> bool:
    text = (raw or "true").strip().lower()
    if text in ("true", ""):
        return True
    if text == "false":
        return False
    raise InputError(
        f"summary must be 'true' or 'false', got '{escape_command(text)}'."
    )


# --- Payload -----------------------------------------------------------------
def load_payload(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputError(f"the linter's output is not JSON ({exc.msg}).") from None
    if not isinstance(data, dict):
        raise InputError("the linter's output is not a JSON object.")
    score = data.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise InputError("the linter's output has no numeric score.")
    if not isinstance(data.get("band"), str):
        raise InputError("the linter's output has no band.")
    checks = data.get("checks")
    if not isinstance(checks, list) or not all(isinstance(c, dict) for c in checks):
        raise InputError("the linter's output has no checks list.")
    return data


# --- Summary -----------------------------------------------------------------
def escape_cell(text: object) -> str:
    # Evidence lines quote file names from the scanned tree, so they are
    # treated as untrusted text: no raw HTML, no table breaks, one line.
    out = str(text)
    out = out.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    out = out.replace("|", "\\|").replace("`", "\\`")
    return " ".join(out.split())


def pattern_link(slug: object) -> str:
    if isinstance(slug, str) and SLUG_RE.match(slug):
        return f"[{slug}]({PATTERNS_URL}#{slug})"
    return escape_cell(slug) if slug else ""


def scored_tail(checks: list) -> str:
    skipped = sum(1 for c in checks if c.get("status") == "NA")
    scored = len(checks) - skipped
    tail = f", {skipped} not applicable" if skipped else ""
    return f"{scored} scored{tail}"


def render_summary(payload: dict, threshold: float | None, gate_message: str) -> str:
    score = float(payload["score"])
    band = payload["band"]
    checks = payload["checks"]
    lines = [
        "## Agent workspace check",
        "",
        f"**Score {format_score(score)}/10, {escape_cell(band)}** ({scored_tail(checks)})",
        "",
    ]
    if threshold is not None:
        verdict = "not met" if gate_message else "met"
        lines += [f"Minimum score {threshold:g}: {verdict}.", ""]
    lines += [
        "| Status | Check | Evidence | Pattern |",
        "| --- | --- | --- | --- |",
    ]
    for check in checks:
        status = check.get("status", "")
        lines.append(
            "| {status} | {cid} | {evidence} | {pattern} |".format(
                status="N/A" if status == "NA" else escape_cell(status),
                cid=escape_cell(check.get("id", "")),
                evidence=escape_cell(check.get("evidence", "")),
                pattern=pattern_link(check.get("pattern")),
            )
        )
    lines += [
        "",
        "Badge for your README:",
        "",
        "```markdown",
        badge_markdown(score, band),
        "```",
        "",
    ]
    return "\n".join(lines)


# --- Runner files ------------------------------------------------------------
def escape_command(text: str) -> str:
    # As @actions/core escapes a workflow-command message, so a value cannot
    # end the line and start a command of its own.
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def format_outputs(outputs: dict) -> str:
    chunks = []
    for name, value in outputs.items():
        delimiter = f"ghadelimiter_{uuid.uuid4()}"
        chunks.append(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
    return "".join(chunks)


def append_file(path: str, text: str) -> None:
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main(argv: list[str] | None = None, env: dict | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    env = os.environ if env is None else env
    try:
        threshold = parse_threshold(env.get("MIN_SCORE"))
        summary_on = parse_summary_flag(env.get("SUMMARY"))
        if argv and argv[0] != "-":
            with open(argv[0], encoding="utf-8") as handle:
                text = handle.read()
        else:
            text = sys.stdin.read()
        payload = load_payload(text)
    except InputError as exc:
        print(f"::error::{exc}")
        return 2

    score = float(payload["score"])
    band = payload["band"]
    code, message = gate(score, threshold)

    output_path = env.get("GITHUB_OUTPUT")
    if output_path:
        append_file(
            output_path,
            format_outputs(
                {
                    "score": format_score(score),
                    "band": band,
                    "badge-markdown": badge_markdown(score, band),
                }
            ),
        )
    summary_path = env.get("GITHUB_STEP_SUMMARY")
    if summary_on and summary_path:
        append_file(summary_path, render_summary(payload, threshold, message))

    print(
        f"Workspace score {format_score(score)}/10, {band} "
        f"({scored_tail(payload['checks'])})"
    )
    if code:
        print(f"::error::{escape_command(message)}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
