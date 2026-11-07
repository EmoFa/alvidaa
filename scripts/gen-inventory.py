#!/usr/bin/env python3
"""Render the firmware inventory (docs/research/inventory.json) into the human tables.

Updates two files, between INVENTORY markers:
  - README.md:                              the tested-models matrix
  - docs/research/10-patched-firmware-playbook.md:       the generation status table

Single source of truth is the JSON — never hand-edit the rendered tables.
Usage: scripts/gen-inventory.py [--check]  (--check fails if output would change)
"""
import json, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
INV = os.path.join(ROOT, "docs", "research", "inventory.json")
README = os.path.join(ROOT, "README.md")
PLAYBOOK = os.path.join(ROOT, "docs", "research", "10-patched-firmware-playbook.md")
TESTED = os.path.join(ROOT, "docs", "research", "TESTED-MODELS.md")

MARK = ("<!-- INVENTORY:START -->", "<!-- INVENTORY:END -->")

def esc(s):
    return str(s).replace("|", "\\|")

def format_contributor(u):
    if isinstance(u, dict):
        name = u.get("name", "")
        url = u.get("url")
        if not url:
            if "github" in u:
                url = f"https://github.com/{u['github']}"
                name = name or f"@{u['github']}"
            elif "reddit" in u:
                url = f"https://reddit.com/user/{u['reddit']}"
                name = name or f"u/{u['reddit']}"
        if url and name:
            return f"[{esc(name)}]({url})"
        return esc(name or url or "")

    s = str(u).strip()
    if s.startswith(("gh:", "github:")):
        h = s.split(":", 1)[1].strip()
        return f"[@{esc(h)}](https://github.com/{h})"
    if s.startswith(("reddit:", "u/")):
        h = s.split(":", 1)[1].strip() if ":" in s else s[2:].strip()
        return f"[u/{esc(h)}](https://reddit.com/user/{h})"
    if s.startswith("@"):
        h = s[1:].strip()
        return f"[@{esc(h)}](https://github.com/{h})"
    if s.startswith("http://") or s.startswith("https://"):
        return f"[{esc(s)}]({s})"
    return f"@{esc(s)}"

def attribution(f):
    names = f.get("tested_by", [])
    return ", ".join(format_contributor(u) for u in names) if names else "community report (name pending)"

def readme_table(fw):
    """Compact matrix for the README.

    The README column is narrow on GitHub, so the full ten-column table wraps
    into an unreadable mess there. This keeps the four things a reader
    actually scans for; the detailed table lives in TESTED-MODELS.md.
    """
    cols = "| Model | Firmware | Launcher | Root | Tested by |"
    sep = "| --- | --- | --- | --- | --- |"
    rows = [
        "| {model} | {id} | {launcher} | {root} | {by} |".format(
            model=esc(short_model(f["model"])), id=esc(f["id"]),
            launcher=short_cap(f["capabilities"].get("launcher", "untested")),
            root=short_cap(f["capabilities"].get("root", "untested")),
            by=attribution(f))
        for f in fw
    ]
    return "\n".join([cols, sep] + rows)


def tested_models_table(fw):
    """Full matrix for TESTED-MODELS.md, where there is room to read it."""
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


def short_model(model):
    """Drop the parenthetical aliases: the README needs the name, not the essay."""
    return model.split(" (")[0].strip()


def short_cap(value):
    """One word for the README: the first token, with the detail left behind."""
    v = str(value).strip()
    if not v:
        return "untested"
    head = v.split(" (")[0].split(",")[0].strip()
    return head if len(head) <= 28 else head[:27] + "\u2026"

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
    tm = open(TESTED).read()
    tm_new = replace_between(tm, *MARK, tested_models_table(fw))

    changed = []
    if rd_new != rd:
        changed.append("README.md")
    if pb_new != pb:
        changed.append("docs/research/10-patched-firmware-playbook.md")
    if tm_new != tm:
        changed.append("docs/research/TESTED-MODELS.md")

    if check:
        if changed:
            print("OUT OF DATE:", ", ".join(changed))
            sys.exit(1)
        print("inventory tables up to date")
        return

    if changed:
        open(README, "w").write(rd_new)
        open(PLAYBOOK, "w").write(pb_new)
        open(TESTED, "w").write(tm_new)
        print("regenerated:", ", ".join(changed))
    else:
        print("no changes")

if __name__ == "__main__":
    main()
