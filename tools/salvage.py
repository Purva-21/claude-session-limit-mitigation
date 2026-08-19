#!/usr/bin/env python3
"""
salvage.py -- work out what state a directory is in after a session was killed
mid-work, and draft the STATE.md you didn't get to write.

Run this FIRST in the fresh session, before you let an agent touch anything. An
abrupt kill can leave a file half-written, a patch script half-applied, or two
artifacts that disagree about which is current. Finding that out by asking an
agent to "just carry on" is how a bad afternoon becomes a bad week.

Usage:
    python3 tools/salvage.py [PATH] [--since MINUTES] [--write-state]

    PATH           directory to inspect (default: current directory)
    --since        treat files modified in the last N minutes as "in flight"
                   (default: 120)
    --write-state  write STATE.draft.md with everything found, as a starting
                   point for the real handoff note

Checks performed
  1. Corrupt or truncated structured files (JSON / ipynb that won't parse)
  2. Files written in the danger window, newest first
  3. Zero-byte files -- the classic signature of a write killed at open()
  4. Duplicate/superseded artifact pairs (foo.ipynb vs foo_patched.ipynb)
  5. Editor and tool leftovers (.tmp, .swp, .partial, .lock)
  6. Git state, if this is a repo: staged, unstaged, untracked
  7. Patch scripts present, and whether they were run after the file they target

Read-only. It changes nothing except the optional STATE.draft.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time

STRUCTURED = (".json", ".ipynb")
LEFTOVER = re.compile(r"(\.tmp|\.temp|\.partial|\.swp|\.lock|~|\.orig|\.rej)$")
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", ".ipynb_checkpoints"}


def walk(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            yield os.path.join(dirpath, name)


def rel(root: str, path: str) -> str:
    return os.path.relpath(path, root)


def check_structured(root: str) -> list:
    bad = []
    for path in walk(root):
        if not path.endswith(STRUCTURED):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                json.load(fh)
        except Exception as exc:
            bad.append((rel(root, path), os.path.getsize(path), str(exc)[:90]))
    return bad


def check_recent(root: str, since_min: int) -> list:
    cutoff = time.time() - since_min * 60
    rows = []
    for path in walk(root):
        try:
            st = os.stat(path)
        except OSError:
            continue
        if st.st_mtime >= cutoff:
            rows.append((rel(root, path), st.st_size, st.st_mtime))
    rows.sort(key=lambda r: -r[2])
    return rows


def check_empty(root: str) -> list:
    return [
        rel(root, p)
        for p in walk(root)
        if os.path.getsize(p) == 0 and not p.endswith("__init__.py")
    ]


def check_leftovers(root: str) -> list:
    return [rel(root, p) for p in walk(root) if LEFTOVER.search(p)]


def check_duplicates(root: str) -> list:
    """Pairs like task.ipynb / task_patched.ipynb / task_v2.ipynb."""
    SUFFIXES = ("_patched", "_fixed", "_new", "_v2", "_final", "_copy", "_old",
                "_backup", "_bak")
    by_stem = {}
    for path in walk(root):
        base, ext = os.path.splitext(os.path.basename(path))
        stem = base
        for suf in SUFFIXES:
            if stem.endswith(suf):
                stem = stem[: -len(suf)]
                break
        by_stem.setdefault((stem, ext), []).append(path)
    out = []
    for (stem, ext), paths in sorted(by_stem.items()):
        if len(paths) > 1:
            entry = []
            for p in sorted(paths, key=lambda q: -os.stat(q).st_mtime):
                st = os.stat(p)
                entry.append((rel(root, p), st.st_size, st.st_mtime))
            out.append((stem + ext, entry))
    return out


def check_git(root: str) -> dict | None:
    if not os.path.isdir(os.path.join(root, ".git")):
        return None
    def g(*args):
        try:
            return subprocess.run(["git", "-C", root] + list(args),
                                  capture_output=True, text=True,
                                  timeout=20).stdout.strip()
        except Exception:
            return ""
    return {
        "head": g("log", "-1", "--oneline"),
        "status": g("status", "--short"),
        "stash": g("stash", "list"),
    }


def check_patch_scripts(root: str) -> list:
    """Patch scripts, and whether their likely target is newer or older."""
    rows = []
    for path in walk(root):
        name = os.path.basename(path)
        if not name.endswith(".py"):
            continue
        if "patch" not in name and "fix" not in name:
            continue
        st = os.stat(path)
        rows.append((rel(root, path), st.st_mtime))
    return sorted(rows, key=lambda r: -r[1])


def fmt_time(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Post-kill triage for a working directory.")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--since", type=int, default=120,
                   help="minutes; files newer than this are 'in flight'")
    p.add_argument("--write-state", action="store_true")
    args = p.parse_args(argv)

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print("not a directory: %s" % root)
        return 2

    lines = []
    def out(s=""):
        print(s)
        lines.append(s)

    out("salvage report for %s" % root)
    out("=" * 70)

    # 1 -----------------------------------------------------------------
    bad = check_structured(root)
    out("\n1. CORRUPT / TRUNCATED STRUCTURED FILES")
    if bad:
        out("   *** These are the ones that matter. A file that no longer")
        out("   *** parses was almost certainly being written when the kill")
        out("   *** landed. Restore from git or re-run the patch script.")
        for path, size, err in bad:
            out("   %-46s %8d B  %s" % (path[:46], size, err))
    else:
        out("   none -- every JSON/ipynb parses")

    # 3 -----------------------------------------------------------------
    empty = check_empty(root)
    out("\n2. ZERO-BYTE FILES")
    if empty:
        out("   A write killed at open() truncates before it writes.")
        for path in empty:
            out("   %s" % path)
    else:
        out("   none")

    # 5 -----------------------------------------------------------------
    left = check_leftovers(root)
    out("\n3. TOOL / EDITOR LEFTOVERS")
    if left:
        for path in left:
            out("   %s" % path)
        out("   (a .tmp or .partial next to a real file often holds the newer content)")
    else:
        out("   none")

    # 2 -----------------------------------------------------------------
    recent = check_recent(root, args.since)
    out("\n4. WRITTEN IN THE LAST %d MINUTES (newest first)" % args.since)
    if recent:
        for path, size, mtime in recent[:20]:
            out("   %s  %8d B  %s" % (fmt_time(mtime), size, path[:48]))
        if len(recent) > 20:
            out("   ... and %d more" % (len(recent) - 20))
        out("\n   The top entry is where the session was when it died.")
    else:
        out("   nothing -- widen --since, or the kill was longer ago")

    # 4 -----------------------------------------------------------------
    dups = check_duplicates(root)
    out("\n5. COMPETING VERSIONS OF THE SAME ARTIFACT")
    if dups:
        out("   Decide which is authoritative BEFORE any agent reads them.")
        for stem, entries in dups:
            out("   %s" % stem)
            for path, size, mtime in entries:
                out("      %s  %8d B  %s" % (fmt_time(mtime), size, path[:44]))
    else:
        out("   none")

    # 7 -----------------------------------------------------------------
    patches = check_patch_scripts(root)
    out("\n6. PATCH SCRIPTS FOUND")
    if patches:
        for path, mtime in patches:
            out("   %s  %s" % (fmt_time(mtime), path))
        out("\n   Re-run these from the pristine input rather than trusting the")
        out("   current output files. That is the point of having them.")
    else:
        out("   none -- if edits were made directly, they cannot be replayed")

    # 6 -----------------------------------------------------------------
    git = check_git(root)
    out("\n7. GIT STATE")
    if git is None:
        out("   not a git repo -- nothing to recover from, and nothing to diff")
        out("   against. `git init && git add -A && git commit` before resuming.")
    else:
        out("   HEAD: %s" % (git["head"] or "(no commits)"))
        if git["status"]:
            out("   uncommitted:")
            for ln in git["status"].splitlines()[:25]:
                out("     %s" % ln)
        else:
            out("   working tree clean")
        if git["stash"]:
            out("   stashes: %s" % git["stash"])

    # ------------------------------------------------------------------
    out("\n" + "=" * 70)
    out("NEXT STEPS")
    out("  1. Fix anything in section 1 -- restore from git, or re-run the")
    out("     patch script from the original input.")
    out("  2. Pick the authoritative version of every pair in section 5 and")
    out("     move the losers into artifacts/.")
    out("  3. Write STATE.md (use --write-state for a starting draft).")
    out("  4. Run tools/prep_workspace.sh before you resume.")
    out("  5. Open the fresh session with prompts/resume.md.")

    if args.write_state:
        draft = os.path.join(root, "STATE.draft.md")
        with open(draft, "w", encoding="utf-8") as fh:
            fh.write("# STATE (draft -- generated by salvage.py, EDIT ME)\n\n")
            fh.write("## Goal\n\n<one sentence: what is this task>\n\n")
            fh.write("## Done\n\n<what is finished AND verified, and how>\n\n")
            fh.write("## Pending\n\n<what remains, in attempt order>\n\n")
            fh.write("## Ruled out\n\n<what failed and WHY -- include numbers; "
                     "this is the expensive part to rediscover>\n\n")
            fh.write("## Open questions\n\n<decisions needed from a human>\n\n")
            fh.write("## Files that matter\n\nRead: <...>\nDo NOT read: <...>\n\n")
            fh.write("---\n\n## Machine findings at time of salvage\n\n```\n")
            fh.write("\n".join(lines))
            fh.write("\n```\n")
        print("\nwrote %s -- the headings are empty on purpose; only you know" % draft)
        print("what was ruled out and why. That section is the valuable one.")

    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
