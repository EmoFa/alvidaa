#!/usr/bin/env python3
"""Render the firmware inventory (docs/inventory.json) into the human tables.

Updates two files, between INVENTORY markers:
  - README.md:                              the tested-models matrix
  - docs/findings/10-...-playbook.md:       the generation status table

Single source of truth is the JSON — never hand-edit the rendered tables.
Usage: scripts/gen-inventory.py [--check]  (--check fails if output would change)
"""
import json, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
INV = os.path.join(ROOT, "docs", "inventory.json")
README = os.path.join(ROOT, "README.md")
PLAYBOOK = os.path.join(ROOT, "docs", "findings", "10-patched-firmware-playbook.md")

MARK = ("<!-- INVENTORY:START -->", "<!-- INVENTORY:END -->")

def attribution(f):
    names = f.get("tested_by", [])
    return ", ".join("@" + esc(u) for u in names) if names else "community report (name pending)"

def esc(s):
    return str(s).replace("|", "\\|")

def readme_table(fw):
    cols = "| Model | Region | SoC | VIDAA OS | Firmware | `transport_protocol` | Browser | Launcher | Root chain | Tested by |"
    sep = "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    rows = [
        "| {model} | {region} | {soc} | {vidaa_os} | {id} | {tp} | {browser} | "
        "{launcher} | {root} | {by} |".format(
            model=esc(f["model"]), region=esc(f.get("region", "?")),
            soc=esc(f["soc"]), vidaa_os=esc(f.get("vidaa_os", "?")),
            id=esc(f["id"]), tp=esc(f.get("transport_protocol", "?")),
            browser=esc(f.get("browser", "?")),
            launcher=f["capabilities"].get("launcher", "untested"),
            root=f["capabilities"].get("root", "untested"),
            by=attribution(f))
        for f in fw
    ]
    return "\n".join([cols, sep] + rows)

def playbook_table(fw):
    cols = "| Generation | SoC | Traversal (`../`) | `fileWrite` | Identity gate | euladpp | Root | Source |"
    sep = "| --- | --- | --- | --- | --- | --- | --- | --- |"
    rows = []
    for f in fw:
        c = f["capabilities"]
        rows.append(
            "| {gen} ({model}, {region}) | {soc} | {trav} | {write} | {gate} | {eula} | {root} | {by} |".format(
                gen=esc(f["id"]), model=esc(f["model"]), region=esc(f.get("region", "?")),
                soc=esc(f["soc"]), trav=c.get("file_bridge_traversal", "untested"),
                write=c.get("file_bridge_write", "untested"),
                gate=c.get("identity_gate", "untested"),
                eula=c.get("euladpp_untar", "untested"),
                root=c.get("root", "untested"),
                by=attribution(f)))
    return "\n".join([cols, sep] + rows)

def replace_between(text, start, end, new):
    s = text.index(start)
    e = text.index(end)
    return text[:s + len(start)] + "\n" + new + "\n" + text[e:]

def main():
    check = "--check" in sys.argv
    inv = json.load(open(INV))
    fw = inv["firmwares"]

    rd = open(README).read()
    rd_new = replace_between(rd, *MARK, readme_table(fw))
    pb = open(PLAYBOOK).read()
    pb_new = replace_between(pb, *MARK, playbook_table(fw))

    changed = []
    if rd_new != rd:
        changed.append("README.md")
    if pb_new != pb:
        changed.append("docs/findings/10-patched-firmware-playbook.md")

    if check:
        if changed:
            print("OUT OF DATE:", ", ".join(changed))
            sys.exit(1)
        print("inventory tables up to date")
        return

    if changed:
        open(README, "w").write(rd_new)
        open(PLAYBOOK, "w").write(pb_new)
        print("regenerated:", ", ".join(changed))
    else:
        print("no changes")

if __name__ == "__main__":
    main()
