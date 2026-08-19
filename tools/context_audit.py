#!/usr/bin/env python3
"""
context_audit.py -- estimate how much context a working directory costs an
agentic coding session.

Why this exists
---------------
In a long agent session, every file the agent has read once becomes a candidate
for re-injection: when the file changes on disk, the harness tends to re-send
its contents so the agent is not reasoning from a stale copy. That is correct
behaviour, but it means the *steady-state* cost of a turn is not the size of
your edit -- it is the size of every large file you have touched and keep
touching. A directory full of 100 KB notebooks and 600-line generators can push
a single turn's input into six figures of tokens, and the session hits its
limit long before the task is finished.

This script does not read your transcript and does not talk to any API. It
looks at a directory and answers one question: if an agent had read these files
and then edited them, how expensive would that be?

Usage
-----
    python3 tools/context_audit.py [PATH] [--turns N] [--json] [--top N]
                                   [--budget TOKENS] [--all]

    PATH       directory to audit (default: current directory)
    --turns    how many edit turns to model per hot file (default: 3)
    --top      how many files to list (default: 15)
    --budget   session input-token budget to compare against (default: 200000)
    --exclude  directory name to treat as out of the agent's reach; repeatable.
               Use this to model "artifacts/ is declared off-limits" -- moving
               a file into a subdirectory does NOT reduce cost by itself, only
               telling the agent to skip it does.
    --json     machine-readable output
    --all      include files that are normally gitignored / binary-ish

Token estimate
--------------
Characters / 3.6, which is a deliberately conservative middle for a mix of
prose, Python and JSON. It is an estimate, not a meter. Ratios between files
are what matter here, not the absolute number.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

CHARS_PER_TOKEN = 3.6

# Extensions an agent typically reads in full and then edits.
HOT_EXT = {
    ".py", ".ipynb", ".md", ".txt", ".json", ".yaml", ".yml", ".toml",
    ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".h",
    ".cpp", ".hpp", ".sql", ".sh", ".r", ".jl", ".tex", ".csv",
}

# Directories that are noise for this purpose.
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache",
    ".pytest_cache", ".ipynb_checkpoints", "dist", "build", ".tox", ".idea",
}

# Thresholds, in estimated tokens, for a single file.
WARN = 4_000     # noticeable
BAD = 12_000     # a single re-injection of this hurts
AWFUL = 25_000   # re-injecting this twice can end a session


def est_tokens(n_chars: int) -> int:
    return int(round(n_chars / CHARS_PER_TOKEN))


def severity(tokens: int) -> str:
    if tokens >= AWFUL:
        return "critical"
    if tokens >= BAD:
        return "high"
    if tokens >= WARN:
        return "medium"
    return "ok"


def notebook_chars(path: str) -> tuple[int, int]:
    """Return (total_chars, chars_excluding_outputs) for a .ipynb.

    Stored cell outputs are the single most common source of accidental
    context bloat: they are invisible in the editor and can be 10x the source.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            nb = json.load(fh)
    except Exception:
        return (os.path.getsize(path), os.path.getsize(path))

    total = os.path.getsize(path)
    src = 0
    for cell in nb.get("cells", []):
        s = cell.get("source", "")
        src += len(s if isinstance(s, str) else "".join(s))
    return (total, src)


def scan(root: str, include_all: bool = False, exclude=()) -> list[dict]:
    excluded = set(exclude)
    rows = []
    for dirpath, dirnames, filenames in os.walk(root):
        if not include_all:
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        dirnames[:] = [d for d in dirnames if d not in excluded]
        for name in filenames:
            path = os.path.join(dirpath, name)
            ext = os.path.splitext(name)[1].lower()
            if not include_all and ext not in HOT_EXT:
                continue
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size == 0:
                continue

            payload = size
            note = ""
            if ext == ".ipynb":
                total, src = notebook_chars(path)
                payload = total
                if total and src and total - src > 20_000:
                    note = (
                        "stored outputs ~%s KB of %s KB -- strip them"
                        % ((total - src) // 1024, total // 1024)
                    )

            tok = est_tokens(payload)
            rows.append(
                {
                    "path": os.path.relpath(path, root),
                    "bytes": size,
                    "tokens": tok,
                    "severity": severity(tok),
                    "note": note,
                }
            )
    rows.sort(key=lambda r: -r["tokens"])
    return rows


def report(rows: list[dict], turns: int, top: int, budget: int) -> dict:
    total_tokens = sum(r["tokens"] for r in rows)
    hot = [r for r in rows if r["tokens"] >= WARN]
    hot_tokens = sum(r["tokens"] for r in hot)
    # Worst realistic case: every hot file is read once, then re-injected on
    # each of `turns` subsequent edits.
    worst = hot_tokens * (1 + turns)
    return {
        "files_scanned": len(rows),
        "total_tokens_if_all_read": total_tokens,
        "hot_files": len(hot),
        "hot_tokens_single_pass": hot_tokens,
        "turns_modelled": turns,
        "worst_case_tokens": worst,
        "budget_tokens": budget,
        "budget_fraction": round(worst / budget, 2) if budget else None,
        "top": rows[:top],
    }


def human(rep: dict) -> str:
    out = []
    a = out.append
    a("context audit")
    a("=" * 62)
    a("files scanned              : %d" % rep["files_scanned"])
    a("hot files (>= %d tok)     : %d" % (WARN, rep["hot_files"]))
    a("one full read of hot files : %s tok" % f"{rep['hot_tokens_single_pass']:,}")
    a(
        "worst case over %d edits   : %s tok"
        % (rep["turns_modelled"], f"{rep['worst_case_tokens']:,}")
    )
    if rep["budget_fraction"] is not None:
        a(
            "vs %s-token budget    : %.1fx"
            % (f"{rep['budget_tokens']:,}", rep["budget_fraction"])
        )
    a("")
    a("%-46s %9s  %s" % ("file", "est tok", "severity"))
    a("-" * 62)
    for r in rep["top"]:
        a("%-46s %9s  %s" % (r["path"][:46], f"{r['tokens']:,}", r["severity"]))
        if r["note"]:
            a("    ^ %s" % r["note"])
    a("")
    crit = [r for r in rep["top"] if r["severity"] in ("critical", "high")]
    if crit:
        a("recommendations")
        a("-" * 62)
        a("1. Move these out of the agent's working directory, or into an")
        a("   artifacts/ subdirectory the agent is told not to read:")
        for r in crit[:6]:
            a("     %s" % r["path"])
        a("2. Strip notebook outputs before the agent touches them:")
        a("     jupyter nbconvert --clear-output --inplace NB.ipynb")
        a("3. Edit large files with a patch script rather than rewriting them.")
        a("4. Delete intermediates as soon as they are consumed.")
    else:
        a("No file in this directory is large enough to dominate a turn.")
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--turns", type=int, default=3)
    p.add_argument("--top", type=int, default=15)
    p.add_argument("--budget", type=int, default=200_000)
    p.add_argument("--exclude", action="append", default=[],
                   help="directory name the agent is told not to read; repeatable")
    p.add_argument("--json", action="store_true")
    p.add_argument("--all", action="store_true")
    args = p.parse_args(argv)

    if not os.path.isdir(args.path):
        print("not a directory: %s" % args.path, file=sys.stderr)
        return 2

    rows = scan(args.path, include_all=args.all, exclude=args.exclude)
    rep = report(rows, args.turns, args.top, args.budget)
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(human(rep))
    # Exit 1 when the modelled worst case exceeds the budget, so this can be
    # used as a pre-flight check in a script.
    return 1 if rep["budget_fraction"] and rep["budget_fraction"] > 1.0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
