#!/usr/bin/env python3
"""Diagnose hisense.es render: full HTML, console, redirects, frames."""
import re, json
from playwright.sync_api import sync_playwright

URL = "https://www.hisense.es/descargas-firmware/100u7q/"
OUT = "hisense_diag"

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = b.new_context(user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0 Safari/537.36")
    pg = ctx.new_page()
    cons = []
    pg.on("console", lambda m: cons.append(f"[{m.type}] {m.text}"))
    pg.on("pageerror", lambda e: cons.append(f"[pageerror] {e}"))
    reqs = []
    pg.on("request", lambda r: reqs.append((r.method, r.url)))
    resps = []
    pg.on("response", lambda r: resps.append((r.status, r.url)))

    resp = pg.goto(URL, wait_until="domcontentloaded", timeout=45000)
    print("FINAL URL:", pg.url)
    print("STATUS:", resp.status if resp else None)
    pg.wait_for_timeout(8000)

    html = pg.content()
    print("HTML LEN:", len(html))
    with open(OUT + ".html", "w") as f:
        f.write(html)
    # frames
    frames = pg.frames
    print("FRAMES:", len(frames), [f.url for f in frames])
    # body text again
    try:
        bt = pg.evaluate("document.body ? document.body.innerText : '(no body)'")
    except Exception as e:
        bt = "(err %s)" % e
    print("BODY TEXT LEN:", len(bt))
    print("BODY TEXT[:800]:", repr(bt[:800]))
    print("CONSOLE:")
    for c in cons[:40]:
        print("  ", c)
    print("REQUESTS (%d):" % len(reqs))
    for m, u in reqs:
        print("  ", m, u)
    with open(OUT + ".meta", "w") as f:
        f.write("URL:%s\n" % pg.url)
        f.write("BODY:%s\n" % bt)
        f.write("CONSOLE:\n" + "\n".join(cons) + "\n")
        f.write("REQUESTS:\n" + "\n".join("%s %s" % (m, u) for m, u in reqs) + "\n")
    b.close()
