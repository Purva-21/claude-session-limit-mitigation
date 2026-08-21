#!/usr/bin/env python3
"""
capture_demo.py -- record docs/img/simulator.gif from index.html.

Steps the simulator once per flush (deterministic - no reliance on the
auto-play timer), twice: once without the fix and once with it. Then:

    ffmpeg -y -framerate 1.8 -i frames/f%03d.png \\
      -vf "scale=900:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3" \\
      -loop 0 docs/img/simulator.gif

Requires playwright and a chromium binary; set EXE below.
"""
from playwright.sync_api import sync_playwright
import pathlib
OUT = pathlib.Path("/tmp/demo/frames")
URL = "file:///root/claude-session-limit-mitigation/index.html"
EXE = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE, args=["--no-sandbox","--force-color-profile=srgb"])
    pg = b.new_page(viewport={"width":1180,"height":1100}, device_scale_factor=2)
    pg.emulate_media(color_scheme="light")
    pg.goto(URL); pg.wait_for_timeout(2200)

    sim = pg.locator(".sim")
    sim.scroll_into_view_if_needed(); pg.wait_for_timeout(300)

    # measure at FULL extent: step to the end, record the box, then reset
    for _ in range(21): pg.click("#step")
    pg.wait_for_timeout(300)
    full = sim.bounding_box()
    pg.click("#reset"); pg.wait_for_timeout(200)
    sim.scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    top = sim.bounding_box()
    clip = {"x":top["x"]-14, "y":top["y"]-14,
            "width":top["width"]+28, "height":full["height"]+28}
    print("clip:", clip)

    n=0
    def shot():
        global n
        pg.screenshot(path=str(OUT/f"f{n:03d}.png"), clip=clip); n+=1

    shot(); shot()
    for _ in range(21):
        pg.click("#step"); pg.wait_for_timeout(110); shot()
    shot(); shot(); shot()

    pg.click("#reset"); pg.wait_for_timeout(150)
    pg.check("#fix"); pg.wait_for_timeout(250)
    sim.scroll_into_view_if_needed(); pg.wait_for_timeout(200)
    shot(); shot()
    for _ in range(21):
        pg.click("#step"); pg.wait_for_timeout(110); shot()
    shot(); shot(); shot(); shot()
    print("frames:", n)
    b.close()
