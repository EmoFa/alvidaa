#!/usr/bin/env python3
"""Render hisense.es firmware page and extract download link(s)."""
import sys, json, re
from playwright.sync_api import sync_playwright

URL = "https://www.hisense.es/descargas-firmware/100u7q/"
OUT = "hisense_100u7q_rendered"

captured = []  # network requests + responses of interest

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--no-sandbox"])
    pg = b.new_page()
    def on_resp(resp):
        u = resp.url
        if re.search(r'\.(zip|bin|pkg|7z|rar|tar\.gz)(\?|$)', u, re.I) or \
           re.search(r'(download|firmware|descarga|admin-ajax|/api/|cdn|cloud|s3|azure)', u, re.I):
            captured.append(("RESP", resp.status, u))
    pg.on("response", on_resp)
    def on_req(req):
        u = req.url
        if re.search(r'(admin-ajax|firmware|descarga|download|/api/)', u, re.I):
            captured.append(("REQ", req.method, u, req.post_data or ""))
    pg.on("request", on_req)

    pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(6000)
    # try to wait for ajax content
    try:
        pg.wait_for_function("document.body.innerText.length > 400", timeout=15000)
    except Exception as e:
        print("warn wait_for_function:", e)
    pg.wait_for_timeout(3000)

    title = pg.title()
    text = pg.inner_text("body")
    # all links
    links = pg.eval_on_selector_all("a", "els => els.map(e => ({href: e.href, text: (e.innerText||'').trim()}))")
    # any elements that look like download buttons
    btns = pg.eval_on_selector_all("a[href*='download'],a[href*='firmware'],a[href*='.zip'],a[href*='.bin'],button",
                                   "els => els.map(e => ({tag:e.tagName, href:e.href||'', text:(e.innerText||'').trim(), cls:e.className||''}))")

    with open(OUT + ".txt", "w") as f:
        f.write("TITLE: " + title + "\n\n")
        f.write("=== BODY TEXT ===\n" + text + "\n\n")
        f.write("=== ALL LINKS ===\n")
        for l in links:
            f.write(f"{l['href']}\t{l['text']}\n")
        f.write("\n=== DOWNLOAD-LIKE ===\n")
        for b2 in btns:
            f.write(f"{b2['tag']} | {b2['href']} | {b2['text']} | {b2['cls']}\n")
        f.write("\n=== NETWORK (filtered) ===\n")
        for c in captured:
            f.write(repr(c) + "\n")
    b.close()

print("=== BODY TEXT (first 2500) ===")
print(text[:2500])
print("\n=== LINKS ===")
for l in links:
    print(l['href'], "|", l['text'][:60])
print("\n=== DOWNLOAD-LIKE ===")
for b2 in btns:
    print(b2['tag'], "|", b2['href'], "|", b2['text'][:60], "|", b2['cls'][:40])
print("\n=== NETWORK (filtered) ===")
for c in captured:
    print(repr(c))
