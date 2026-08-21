#!/usr/bin/env python3
"""
build.py -- one source, two outputs.

site/_content.html is the single source for the visual explainer. It is written
WITHOUT a document wrapper because the Artifact host supplies one. This script
wraps it for GitHub Pages and writes index.html at the repository root.

    python3 site/build.py

Run it after editing site/_content.html; never edit index.html by hand.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC  = os.path.join(HERE, "_content.html")
OUT  = os.path.join(ROOT, "index.html")

body = open(SRC, encoding="utf-8").read()

m = re.search(r"<title>(.*?)</title>", body, re.S)
title = m.group(1).strip() if m else "The Pending Set"
body = re.sub(r"<title>.*?</title>\s*", "", body, count=1, flags=re.S)

DESC = ("A resync queue in an agentic coding harness that never drains: where it "
        "comes from, how it grows, and the one action that clears it. Measured "
        "across 296 turns of a single session.")

page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{DESC}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{DESC}">
<meta property="og:type" content="article">
<meta name="twitter:card" content="summary_large_image">
<style>*,*::before,*::after{{box-sizing:border-box}}body{{margin:0}}</style>
</head>
<body>
{body}
</body>
</html>
"""

open(OUT, "w", encoding="utf-8").write(page)
print("wrote %s  (%d bytes)" % (os.path.relpath(OUT, ROOT), len(page)))
print("title:", title)
