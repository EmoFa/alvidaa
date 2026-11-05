# Documentation map

The repository root is the launcher product. Root research is filed by model
and firmware, with cross-model material kept separate.

**Rendered site:** <https://carteakey.github.io/alvidaa/> — the same pages with
a filterable index. Generated from this tree by
[`../scripts/gen-site.py`](../scripts/gen-site.py); nothing is duplicated.

| Directory | What lives there |
|---|---|
| [`models/`](models/README.md) | Model- and firmware-specific root guides, evidence and modding notes. Start with the exact model **and** firmware string. |
| [`research/`](research/) | Cross-model material: the firmware inventory, method catalogue, tested-models guide and the patched-firmware playbook. |
| [`launcher/`](launcher/) | Launcher deployment and the on-TV launcher v2 roadmap. |
| [`project/`](project/) | The project story and the AI prompt ladder. |
| [`../tools/`](../tools/) | The scripts the guides reference — pairing, installers, build helpers. |

## Where to start

| If you want to… | Read |
|---|---|
| replace your home screen, no root | [the launcher quickstart](../README.md#quickstart--the-launcher) |
| root the TV | [`models/`](models/README.md) — match model **and** firmware, then [`../SECURITY.md`](../SECURITY.md) |
| see what works on which TV | [the tested-model matrix](../README.md#tested-models) and [`research/EXPLOITS.md`](research/EXPLOITS.md) |
| report your TV | [`research/TESTED-MODELS.md`](research/TESTED-MODELS.md) — PR, not issue |
| understand how it was found | [`project/STORY.md`](project/STORY.md) and the [prompt ladder](project/HACK-YOUR-OWN.md) |
| work on the launcher itself | [`launcher/DEPLOY.md`](launcher/DEPLOY.md), [`launcher/LANES.md`](launcher/LANES.md) |

## Cross-model references

- [`research/inventory.json`](research/inventory.json) — firmware compatibility data (single source of truth)
- [`research/exploits.json`](research/exploits.json) — method catalogue data
- [`research/EXPLOITS.md`](research/EXPLOITS.md) — generated method inventory
- [`research/TESTED-MODELS.md`](research/TESTED-MODELS.md) — how to report a TV
- [`research/10-patched-firmware-playbook.md`](research/10-patched-firmware-playbook.md) — generations where the `../` bridge route is closed

Both JSON files are the source; the tables are generated. Edit the JSON and run
`scripts/gen-inventory.py` / `scripts/gen-exploits.py`, then `scripts/check.sh`.

See [SECURITY.md](../SECURITY.md) for the disclosure stance and
[AGENTS.md](../AGENTS.md) for the rules an AI session follows.
