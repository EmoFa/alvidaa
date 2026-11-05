#!/usr/bin/env python3
"""Scaffold a tested-model report: inventory row + model guide skeleton.

Walks the flow a PR needs, catching the mistakes reviews kept finding
(wrong tree layout, duplicate firmware row, mislabelled fields):

  1. collect model / firmware / SoC / region (flags or prompts)
  2. validate the firmware string against the id grammar
  3. refuse duplicates (same logic as check.sh step 8) with a pointer
     at the existing row
  4. scaffold docs/models/<Model>/<FW>/{README,EVIDENCE,MODDING}.md
  5. add the hand-maintained index row in docs/models/README.md
  6. append the inventory row (capabilities default to "untested")
  7. run both generators and scripts/check.sh

Usage:
  scripts/report.py                          # fully interactive
  scripts/report.py --model 50A61HUV --firmware 'V0000.09.01O.P0815' ...

Exit 0 = scaffolded and verified; 1 = refused or checks failed. Files are
created but nothing is committed — review the diff, then open the PR.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INV = ROOT / "docs" / "research" / "inventory.json"
MODELS = ROOT / "docs" / "models"
MODELS_INDEX = MODELS / "README.md"

# Every inventory id so far matches this: optional V prefix, a 2-digit
# (09.01O.P0813) or 4-digit (V0000.09.60I.Q0813) major, then minor + letter
# groups, optionally followed by a qualifier.
FIRMWARE_RE = re.compile(r"^(?:V\d{2,4}\.)?\d{2}\.\d{2}[A-Z]\.[A-Z]\d{4}(\s*\(.*\))?$")


def norm_id(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def base_fw(s):
    base = norm_id(re.sub(r"\(.*$", "", s).strip())
    # the vendor V-string and the shorthand are the same firmware:
    # V0000.09.60W.Q0612 == 09.60W.Q0612
    return re.sub(r"^v\d{2,4}\.", "", base)


def norm_model(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_rows():
    inv = json.loads(INV.read_text(encoding="utf-8"))
    rows = []
    for f in inv["firmwares"]:
        rows.append({
            "nid": norm_id(f["id"]),
            "base": base_fw(f["id"]),
            "nm": norm_model(f.get("model", "")),
            "id": f["id"],
            "model": f.get("model", "?"),
        })
    return inv, rows


def duplicate_check(rows, firmware, model):
    """Return (blockers, warnings) for the proposed row."""
    nid, base, nm = norm_id(firmware), base_fw(firmware), norm_model(model)
    blockers, warnings = [], []
    for r in rows:
        if r["nid"] == nid:
            blockers.append(f"firmware id {firmware!r} is already recorded as row "
                            f"{r['id']!r} (model {r['model']!r})")
        elif r["base"] == base and nm and r["nm"] and (nm in r["nm"] or r["nm"] in nm):
            blockers.append(f"firmware {base!r} already has row {r['id']!r} whose model "
                            f"{r['model']!r} aliases {model!r} — same device?")
        elif r["base"] == base:
            warnings.append(f"firmware base {base!r} already exists as {r['id']!r} "
                            f"(model {r['model']!r}) — different model, keep the "
                            f"qualifier that disambiguates the id")
    return blockers, warnings


def ask(args, name, prompt, required=True, default=""):
    val = getattr(args, name, None)
    if val:
        return val
    hint = f" [{default}]" if default else ""
    suffix = "" if required else " (optional)"
    val = input(f"{prompt}{hint}{suffix}: ").strip()
    while required and not val:
        val = input(f"{prompt} is required: ").strip()
    return val or default


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", help="TV model, e.g. 50A61HUV")
    ap.add_argument("--firmware", help="firmware id, e.g. 'V0000.09.01O.P0815' or "
                                       "'09.60X.Q0609 (2026-06)'")
    ap.add_argument("--soc", help="SoC, e.g. MTK9602")
    ap.add_argument("--region", help="region, e.g. EU_A / US/CAN / India")
    ap.add_argument("--vidaa-os", dest="vidaa_os", default="", help='VIDAA OS, e.g. "U09.01"')
    ap.add_argument("--browser", default="", help='browser, e.g. "Chromium 111 \\"odin\\""')
    ap.add_argument("--transport", dest="transport", default="", help="transport_protocol value")
    ap.add_argument("--build-date", dest="build_date", default="", help="build date, YYYY-MM-DD")
    ap.add_argument("--tested-by", dest="tested_by", default="",
                    help="reporter handle (gh:name or reddit:name, comma-separated)")
    ap.add_argument("--yes", action="store_true", help="skip the final confirmation")
    args = ap.parse_args()

    model = ask(args, "model", "TV model")
    firmware = ask(args, "firmware", "Firmware id (as shown in TV system info)")
    soc = ask(args, "soc", "SoC")
    region = ask(args, "region", "Region", required=False, default="?")

    if not FIRMWARE_RE.match(firmware):
        print(f"REFUSED: firmware {firmware!r} does not match the inventory id grammar "
              f"(optional 'V<major>.' prefix + <2 digits>.<2 digits><letter>."
              f"<letter><4 digits> + optional ' (qualifier)')")
        return 1

    inv, rows = load_rows()
    blockers, warnings = duplicate_check(rows, firmware, model)
    for w in warnings:
        print(f"WARNING: {w}")
    for b in blockers:
        print(f"REFUSED: {b}")
    if blockers:
        print("If this is genuinely a new device, disambiguate the id qualifier "
              "or correct the model — do not add a second row for one (device, firmware).")
        return 1
    if warnings and not args.yes:
        if input("Proceed anyway? [y/N] ").strip().lower() not in ("y", "yes"):
            print("aborted")
            return 1

    # dir name keeps the original case (existing guides: 09.01O.P0813, ...)
    fw_dir_name = re.sub(r"\s*\(.*$", "", firmware).strip()
    guide = MODELS / model / fw_dir_name
    if guide.exists():
        print(f"REFUSED: guide directory {guide.relative_to(ROOT)} already exists")
        return 1

    vida = ask(args, "vidaa_os", "VIDAA OS string", required=False, default="?")
    browser = ask(args, "browser", "Browser", required=False, default="?")
    transport = ask(args, "transport", "transport_protocol value", required=False, default="?")
    build_date = ask(args, "build_date", "Build date (YYYY-MM-DD)", required=False, default="?")
    tested_by = [h.strip() for h in args.tested_by.split(",") if h.strip()] if args.tested_by else []

    rel = guide.relative_to(MODELS).as_posix()
    guide_row = (f"| `{model}` | `{fw_dir_name}` (VIDAA `{vida}`, {region}) | {soc} "
                 f"| TODO: root method | TODO: persistence "
                 f"| [README]({rel}/README.md) · [EVIDENCE]({rel}/EVIDENCE.md) "
                 f"· [MODDING]({rel}/MODDING.md) |")

    print(f"\n==> scaffolding {guide.relative_to(ROOT)}/")
    guide.mkdir(parents=True)
    (guide / "README.md").write_text(
        f"# {model} — {firmware}\n\n"
        f"- **Model:** {model}\n- **Firmware:** {firmware}\n- **SoC:** {soc}\n"
        f"- **Region:** {region}\n- **VIDAA OS:** {vida}\n- **Browser:** {browser}\n"
        f"- **Reported by:** {', '.join(tested_by) or 'TODO'}\n\n"
        "TODO: root chain summary. Keep claims labelled (verified / community "
        "reported / hypothesis) and link evidence.\n", encoding="utf-8")
    (guide / "EVIDENCE.md").write_text(
        f"# {model} {firmware} — evidence ledger\n\n"
        "| Claim | Evidence | Source |\n| --- | --- | --- |\n"
        "| TODO | TODO | TODO |\n", encoding="utf-8")
    (guide / "MODDING.md").write_text(
        f"# {model} {firmware} — modding notes\n\n"
        "TODO: launcher/install notes for this model+firmware.\n", encoding="utf-8")

    index = MODELS_INDEX.read_text(encoding="utf-8")
    marker = "\n\nThis table is hand-maintained"
    if marker not in index:
        print("REFUSED: docs/models/README.md index marker not found — add the row manually")
        return 1
    MODELS_INDEX.write_text(index.replace(marker, f"\n{guide_row}{marker}"), encoding="utf-8")
    print(f"==> index row added to docs/models/README.md")

    inv["firmwares"].append({
        "id": firmware,
        "model": model,
        "region": region,
        "soc": soc,
        "vidaa_os": vida,
        "transport_protocol": transport,
        "browser": browser,
        "build_date": build_date,
        "tested_by": tested_by,
        "capabilities": {
            "pairing": "untested",
            "launcher": "untested",
            "file_bridge_traversal": "untested",
            "file_bridge_write": "untested",
            "identity_gate": "untested",
            "euladpp_untar": "untested",
            "root": "untested",
            "notes": "scaffolded by scripts/report.py — fill from the report",
        },
    })
    INV.write_text(json.dumps(inv, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("==> inventory row appended (all capabilities 'untested' — edit before PR)")

    if not args.yes:
        if input("\nRun generators + check.sh now? [Y/n] ").strip().lower() in ("n", "no"):
            print("skipped — run scripts/gen-inventory.py && scripts/gen-exploits.py && "
                  "scripts/check.sh before opening the PR")
            return 0

    print("==> generators + check")
    for cmd in (["python3", "scripts/gen-inventory.py"],
                ["python3", "scripts/gen-exploits.py"],
                ["bash", "scripts/check.sh"]):
        print(f"   $ {' '.join(cmd)}")
        if subprocess.run(cmd, cwd=str(ROOT)).returncode != 0:
            print(f"FAILED: {' '.join(cmd)} — fix before opening the PR "
                  f"(git checkout -- <files> reverts the scaffold)")
            return 1

    print("\nScaffolded. Next: fill the TODOs in the guide + inventory row, "
          "commit, open the PR. `git checkout -- docs/research/inventory.json "
          "docs/models/README.md && rm -rf docs/models/" + model + "` reverts everything.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
