# Documentation map

The repository root is the launcher product. Root research is filed by model
and firmware, with cross-model material kept separate.

| Directory | What lives there |
|---|---|
| [`models/`](models/README.md) | Model- and firmware-specific root guides, evidence and modding notes. Start with the exact model **and** firmware string. |
| [`research/`](research/) | Cross-model material: the firmware inventory, method catalogue, tested-models guide and the patched-firmware playbook. |
| [`launcher/`](launcher/) | Launcher deployment and the on-TV launcher v2 roadmap. |
| [`project/`](project/) | The project story, the AI prompt ladder and the blog draft. |

## Model guides

| Model | Firmware | Guide |
|---|---|---|
| `50A51HUV` | `09.01O.P0813` | [`models/50A51HUV/09.01O.P0813/README.md`](models/50A51HUV/09.01O.P0813/README.md) |
| `HE40E5600FFWTS` | `V0100.01.00A.N0410` | [`models/HE40E5600FFWTS/V0100.01.00A.N0410/README.md`](models/HE40E5600FFWTS/V0100.01.00A.N0410/README.md) |
| `100U7Q` (`100U70QEVS`) | `V0000.09.60I.Q0813` | [`models/100U7Q/V0000.09.60I.Q0813/README.md`](models/100U7Q/V0000.09.60I.Q0813/README.md) |

## Cross-model references

- [`research/inventory.json`](research/inventory.json) — firmware compatibility data (single source of truth)
- [`research/exploits.json`](research/exploits.json) — method catalogue data
- [`research/EXPLOITS.md`](research/EXPLOITS.md) — generated method inventory
- [`research/TESTED-MODELS.md`](research/TESTED-MODELS.md) — how to report a TV
- [`research/10-patched-firmware-playbook.md`](research/10-patched-firmware-playbook.md) — generations where the `../` bridge route is closed

See [SECURITY.md](../SECURITY.md) for the disclosure stance and
[AGENTS.md](../AGENTS.md) for the rules an AI session follows.
