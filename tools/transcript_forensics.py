#!/usr/bin/env python3
"""
transcript_forensics.py -- find out where a session's input tokens actually
went, by reading the session transcript rather than guessing.

context_audit.py measures *exposure* (what a directory could cost).
This measures what a session *did* cost, and attributes it.

Usage:
    python3 tools/transcript_forensics.py TRANSCRIPT.jsonl
    python3 tools/transcript_forensics.py TRANSCRIPT.jsonl --json

    Transcripts are JSONL, one record per line. Claude Code writes them under
    ~/.claude/projects/<slug>/<session-id>.jsonl -- find yours with:
        ls -t ~/.claude/projects/*/*.jsonl | head

What it reports
  1. Attachment volume by kind -- which non-conversation payloads dominate
  2. File re-injections: every time a file already in context was re-sent
  3. What tool call preceded each re-injection (the trigger)
  4. DUPLICATE re-injections: identical content sent more than once
  5. Amplification: re-injected bytes vs the edit that caused them
  6. The control: how many Edit/Write calls did NOT trigger a re-injection

Record shapes vary between harness versions. Unknown shapes are counted as
"unrecognised" rather than silently dropped -- if that number is large, the
parser needs updating for your version, and the totals are undercounts.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys

CHARS_PER_TOKEN = 3.6

# Attachment kinds that carry file contents back into context.
FILE_KINDS = {"edited_text_file", "file", "new_file_reference", "read_file"}


def load(path: str):
    recs, bad = [], 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                recs.append(json.loads(line))
            except Exception:
                bad += 1
    return recs, bad


def tool_uses(rec) -> list:
    msg = rec.get("message")
    if not isinstance(msg, dict):
        return []
    out = []
    for block in msg.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            inp = block.get("input") or {}
            label = inp.get("description") or inp.get("file_path") or ""
            out.append((block.get("name"), str(label)[:70]))
    return out


def attachment_text(att: dict) -> str:
    """Best-effort extraction of the payload an attachment injects."""
    for key in ("snippet", "content", "text"):
        val = att.get(key)
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            inner = val.get("file")
            if isinstance(inner, dict) and isinstance(inner.get("content"), str):
                return inner["content"]
            if isinstance(val.get("content"), str):
                return val["content"]
    return ""


def analyse(recs: list) -> dict:
    kinds = collections.Counter()
    kind_bytes = collections.Counter()
    unrecognised = 0

    reinjections = []
    last_tools: list = []
    edit_calls = 0
    bash_calls = 0

    for rec in recs:
        rtype = rec.get("type")

        if rtype == "assistant":
            tu = tool_uses(rec)
            if tu:
                last_tools = tu
                for name, _ in tu:
                    if name in ("Edit", "Write", "NotebookEdit"):
                        edit_calls += 1
                    elif name == "Bash":
                        bash_calls += 1

        elif rtype == "attachment":
            att = rec.get("attachment")
            if not isinstance(att, dict):
                unrecognised += 1
                continue
            kind = att.get("type", "unknown")
            payload = attachment_text(att)
            kinds[kind] += 1
            kind_bytes[kind] += len(payload) or len(json.dumps(att))

            if kind in FILE_KINDS:
                reinjections.append({
                    "kind": kind,
                    "file": att.get("filename") or att.get("filePath") or "?",
                    "bytes": len(payload),
                    "lines": payload.count("\n") + 1 if payload else 0,
                    "hash": hashlib.md5(payload.encode()).hexdigest()[:8],
                    "trigger": sorted({n for n, _ in last_tools}),
                    "ts": rec.get("timestamp", ""),
                })

    # duplicates: same file + identical content, sent more than once
    seen = collections.Counter((r["file"], r["hash"]) for r in reinjections)
    dupes = {k: v for k, v in seen.items() if v > 1}
    dupe_bytes = 0
    for (fname, h), n in dupes.items():
        size = next(r["bytes"] for r in reinjections
                    if r["file"] == fname and r["hash"] == h)
        dupe_bytes += size * (n - 1)

    total = sum(r["bytes"] for r in reinjections)
    return {
        "records": len(recs),
        "attachment_kinds": dict(kinds),
        "attachment_bytes": dict(kind_bytes),
        "unrecognised_attachments": unrecognised,
        "reinjections": reinjections,
        "reinjection_count": len(reinjections),
        "reinjection_bytes": total,
        "reinjection_tokens": int(total / CHARS_PER_TOKEN),
        "duplicate_events": sum(v - 1 for v in dupes.values()),
        "duplicate_bytes": dupe_bytes,
        "edit_calls": edit_calls,
        "bash_calls": bash_calls,
        "by_trigger": dict(collections.Counter(
            ",".join(r["trigger"]) or "(none)" for r in reinjections)),
        "bytes_by_trigger": dict(collections.Counter({
            k: sum(r["bytes"] for r in reinjections
                   if (",".join(r["trigger"]) or "(none)") == k)
            for k in {",".join(r["trigger"]) or "(none)" for r in reinjections}
        })),
    }


def human(a: dict) -> str:
    L = []
    p = L.append
    p("transcript forensics")
    p("=" * 72)
    p("records parsed            : %d" % a["records"])
    if a["unrecognised_attachments"]:
        p("unrecognised attachments  : %d  (totals are undercounts)"
          % a["unrecognised_attachments"])

    p("\nATTACHMENT VOLUME BY KIND")
    for kind, b in sorted(a["attachment_bytes"].items(), key=lambda kv: -kv[1]):
        p("  %-26s n=%-4d %9d B" % (kind, a["attachment_kinds"][kind], b))

    p("\nFILE RE-INJECTIONS")
    p("  events                  : %d" % a["reinjection_count"])
    p("  bytes                   : %d  (~%d tokens)"
      % (a["reinjection_bytes"], a["reinjection_tokens"]))
    p("  duplicated events       : %d  (%d B of identical content re-sent)"
      % (a["duplicate_events"], a["duplicate_bytes"]))

    if a["reinjections"]:
        p("\n  %-40s %8s %7s  %s" % ("file", "bytes", "lines", "after tool"))
        p("  " + "-" * 70)
        for r in a["reinjections"]:
            p("  %-40s %8d %7d  %s"
              % (os.path.basename(r["file"])[:40], r["bytes"], r["lines"],
                 ",".join(r["trigger"])))

    p("\nBY TRIGGERING TOOL")
    for k, n in sorted(a["by_trigger"].items(), key=lambda kv: -kv[1]):
        p("  %-24s n=%-3d  %8d B" % (k, n, a["bytes_by_trigger"].get(k, 0)))

    p("\nTHE CONTROL")
    p("  Edit/Write calls        : %d" % a["edit_calls"])
    p("  Bash calls              : %d" % a["bash_calls"])
    p("  re-injection events     : %d" % a["reinjection_count"])
    p("")
    p("  If re-injections cluster after Bash and not after Edit/Write, the")
    p("  harness is re-syncing files it could not track being changed. The")
    p("  fix is to make in-context edits with the Edit tool, and to keep")
    p("  script-mediated edits pointed at files that were never read.")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Attribute a session's input cost.")
    ap.add_argument("transcript")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.transcript):
        print("no such transcript: %s" % args.transcript, file=sys.stderr)
        print("try: ls -t ~/.claude/projects/*/*.jsonl | head", file=sys.stderr)
        return 2

    recs, bad = load(args.transcript)
    if bad:
        print("(%d unparseable lines skipped)" % bad, file=sys.stderr)
    a = analyse(recs)
    print(json.dumps(a, indent=2) if args.json else human(a))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
