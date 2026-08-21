# site/

`_content.html` is the **single source** for the visual explainer published at
[the GitHub Pages site](../index.html) and as a hosted artifact.

It deliberately has no `<!doctype>`, `<html>`, `<head>` or `<body>` — the
artifact host supplies those. `build.py` wraps it for GitHub Pages.

```bash
python3 site/build.py     # regenerates index.html at the repo root
```

**Never edit `index.html` by hand.** It is generated, and a hand edit will be
overwritten on the next build. Edit `_content.html` and rebuild.
