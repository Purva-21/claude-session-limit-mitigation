#!/usr/bin/env python3
"""
gemini_telemetry_parse.py -- pull per-turn input-token deltas and tool calls out
of a Gemini CLI local telemetry log.

    python3 tools/gemini_telemetry_parse.py .gemini/telemetry.log

Enable the log first (there is NO default file output):

    .gemini/settings.json
    {"telemetry": {"enabled": true, "target": "local",
                   "outfile": ".gemini/telemetry.log"}}

What it looks for
  * gemini_cli.token.usage    -- counts tagged input / output / thought / cache / tool
  * gen_ai.client.token.usage -- the OTEL semantic-convention equivalent
  * gemini_cli.tool_call      -- function name, duration, success

and interleaves them so you can see which tool call preceded a jump in input
tokens.

------------------------------------------------------------------------------
IMPORTANT -- READ BEFORE TRUSTING THE OUTPUT

This parser was written from the telemetry documentation, NOT against a real
log file, because no Gemini CLI installation was available where it was
written. OpenTelemetry exporters vary in shape between versions and targets.

It is therefore deliberately forgiving: it walks arbitrary nested JSON looking
for the known metric and attribute names rather than assuming a schema, and it
reports how much it could not interpret. If `unparsed lines` is large, or the
totals look wrong against `/stats`, believe /stats and not this script -- then
please open an issue with a redacted sample so the parser can be fixed.

Treat its numbers as a convenience, and `/stats` as the source of truth.
------------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import json
import os
import sys

TOKEN_METRICS = ("gemini_cli.token.usage", "gen_ai.client.token.usage")
TOOL_EVENT = "gemini_cli.tool_call"
TYPE_KEYS = ("type", "token_type", "gen_ai.token.type", "kind")
NAME_KEYS = ("function_name", "tool_name", "name", "gen_ai.tool.name")


def walk(obj):
    """Yield every dict nested anywhere inside obj."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


def flatten_attrs(d: dict) -> dict:
    """OTEL attributes appear as dicts, or as [{key, value:{stringValue|intValue}}]."""
    out = {}
    for key in ("attributes", "attrs", "tags"):
        a = d.get(key)
        if isinstance(a, dict):
            out.update({str(k): v for k, v in a.items()})
        elif isinstance(a, list):
            for item in a:
                if not isinstance(item, dict):
                    continue
                k = item.get("key")
                v = item.get("value")
                if isinstance(v, dict):
                    v = next((v[x] for x in
                              ("stringValue", "intValue", "doubleValue", "boolValue")
                              if x in v), v)
                if k is not None:
                    out[str(k)] = v
    for k, v in d.items():
        if isinstance(v, (str, int, float)) and k not in out:
            out[k] = v
    return out


def first(d: dict, keys) -> str | None:
    for k in keys:
        if k in d and d[k] is not None:
            return str(d[k])
    return None


def numeric(d: dict):
    for k in ("value", "asInt", "asDouble", "count", "sum", "tokenCount", "tokens"):
        v = d.get(k)
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, str) and v.lstrip("-").isdigit():
            return int(v)
    return None


def parse(path: str) -> dict:
    events, unparsed, raw_lines = [], 0, 0

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        blob = fh.read()

    # The log may be JSONL, or a stream of pretty-printed JSON objects.
    chunks = []
    for line in blob.splitlines():
        line = line.strip()
        if line.startswith("{"):
            chunks.append(line)
    if not chunks:
        decoder = json.JSONDecoder()
        idx = 0
        while idx < len(blob):
            idx = blob.find("{", idx)
            if idx < 0:
                break
            try:
                obj, end = decoder.raw_decode(blob, idx)
                chunks.append(json.dumps(obj))
                idx = end
            except ValueError:
                idx += 1

    for chunk in chunks:
        raw_lines += 1
        try:
            top = json.loads(chunk)
        except Exception:
            unparsed += 1
            continue

        matched = False
        for node in walk(top):
            name = first(node, ("name", "metric", "event.name", "body"))
            if not name:
                continue
            attrs = flatten_attrs(node)

            if any(m in str(name) for m in TOKEN_METRICS):
                val = numeric(node) or numeric(attrs) or 0
                events.append({
                    "kind": "tokens",
                    "type": first(attrs, TYPE_KEYS) or "unknown",
                    "value": val,
                    "session": attrs.get("sessionId") or attrs.get("session.id"),
                })
                matched = True
            elif TOOL_EVENT in str(name):
                events.append({
                    "kind": "tool",
                    "name": first(attrs, NAME_KEYS) or "?",
                    "success": attrs.get("success"),
                    "session": attrs.get("sessionId") or attrs.get("session.id"),
                })
                matched = True
        if not matched:
            unparsed += 1

    return {"events": events, "unparsed": unparsed, "records": raw_lines}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("logfile")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.logfile):
        print("no such file: %s" % args.logfile, file=sys.stderr)
        print("did you set telemetry.outfile in .gemini/settings.json?",
              file=sys.stderr)
        return 2

    res = parse(args.logfile)
    if args.json:
        print(json.dumps(res, indent=2))
        return 0

    ev = res["events"]
    print("gemini telemetry parse")
    print("=" * 66)
    print("records seen      : %d" % res["records"])
    print("uninterpreted     : %d%s" % (
        res["unparsed"],
        "   <-- large? trust /stats instead, and file an issue"
        if res["unparsed"] > res["records"] // 2 else ""))
    print("events extracted  : %d" % len(ev))

    if not ev:
        print("\nNothing recognised. Either telemetry is not writing to this file,")
        print("or the schema differs in your version. Fall back to /stats deltas —")
        print("they are coarser but they are real.")
        return 1

    totals = {}
    for e in ev:
        if e["kind"] == "tokens":
            totals[e["type"]] = totals.get(e["type"], 0) + (e["value"] or 0)

    print("\nTOKENS BY TYPE")
    for k, v in sorted(totals.items(), key=lambda kv: -kv[1]):
        print("  %-12s %12s" % (k, f"{v:,}"))
    print("\n  'input' is the one that matters for this test. If a resync is")
    print("  happening, input jumps on the shell-edit turn and not on the")
    print("  native-edit turn. If 'cache' rises instead, it is re-sending but")
    print("  the provider is caching it — a different and interesting result.")

    print("\nTIMELINE (tool calls interleaved with token events)")
    print("-" * 66)
    run = 0
    for e in ev:
        if e["kind"] == "tool":
            print("  tool   %-28s success=%s" % (e["name"][:28], e["success"]))
        else:
            run += e["value"] or 0
            print("  tokens %-10s +%-10s (running %s)"
                  % (e["type"], f"{e['value']:,}", f"{run:,}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
