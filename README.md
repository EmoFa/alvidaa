# alvidaa

![alvidaa launcher, live on a Hisense VIDAA TV — clock, inputs with live
signal, and real app icons, captured from the TV itself](docs/img/launcher-home.png)

Two projects in one repo. Both started on one TV over a single weekend; the
root half now runs on seven different chips, and the launcher no longer
needs a server at all.

1. **A launcher** — a self-installed, self-hosted home screen for Hisense
   **VIDAA** TVs: a clock, your HDMI inputs with live signal, your real
   apps. Nothing sponsored. The TV installs the page itself as a native
   app through its own hidden APIs.
2. **Root** — and more importantly: the first publicly documented root
   path for 2024+ VIDAA firmware (as far as public record shows). A
   browser-exposed file bridge, a sandbox escape found by reading an
   errno, a production boot hook, and a key-only SSH shell — no hardware,
   no flashed partitions, verified boot still green.

Everything runs on a TV you own, through the TV's own APIs, and every
step is designed to be undone. Built with — and designed for — AI coding
sessions: point your agent at [AGENTS.md](AGENTS.md); the prompt ladder
that worked is in [the prompt ladder](docs/project/HACK-YOUR-OWN.md).

**Read it as a site:** <https://carteakey.github.io/alvidaa/> — the same
markdown, rendered with the tested-model matrix, the model guides and the
method catalogue in one place. Generated from the repo by
[`scripts/gen-site.py`](scripts/gen-site.py); nothing is moved or duplicated.

## Start here

| If you want to… | Go to |
| --- | --- |
| **replace your home screen** — no root, reversible | [Quickstart — the launcher](#quickstart--the-launcher) |
| **root the TV** | [docs/models/](docs/models/) — match your model *and* firmware string, then read [SECURITY.md](SECURITY.md) |
| **see what works on which TV** | [Tested models](#tested-models) and [EXPLOITS.md](docs/research/EXPLOITS.md) |
| **contribute a report** | [TESTED-MODELS.md](docs/research/TESTED-MODELS.md) — PR, not issue |

## The two lanes

```
LANE 1 — the launcher (no root needed)

┌─────────────┐   WebSocket    ┌──────────────────┐   MQTT/TLS 36669   ┌─────────┐
│ TV browser  │ ◄────────────► │ server (Pi)      │ ◄────────────────► │ VIDAA   │
│ canvas page │  JSON pushes   │ config + watcher │  RemoteNow control │ TV      │
└─────────────┘                └──────────────────┘                    └─────────┘

LANE 2 — the root chain (see the 50A51HUV guide)

cert-gated MQTT ─► browser file bridge ─► ../ escape ─► unauth local API
    ─► rc.local boot hook ─► root at every boot ─► key-only SSH
```

Lane 1 has been tested on the model below; compatibility with other models
and firmware remains to be established. Lane 2 is **model-specific** (SoC and
partition layout bite there) and is documented
stage by stage in [the 50A51HUV guide](docs/models/50A51HUV/09.01O.P0813/README.md).

## Quickstart — the launcher

```sh
# 1. the 2024 client cert (the full story: docs/models/50A51HUV/09.01O.P0813/findings/01-mqtt-bridge.md)
#    unzip res/raw/client_mobile_android.p12 from the VIDAA Smart TV APK, then
openssl pkcs12 -legacy -in client_mobile_android.p12 \
  -passin pass:186e990688070325a1c4b0ce275d2388 \
  -clcerts -nokeys -out server/keys/vidaa_cert.pem
openssl pkcs12 -legacy -in client_mobile_android.p12 \
  -passin pass:186e990688070325a1c4b0ce275d2388 \
  -nocerts -nodes -out server/keys/vidaa_key.pem

# 2. pair (TV shows a 4-digit code; type it when asked)
cd server && python3 -m venv venv && ./venv/bin/pip install paho-mqtt
TV_MAC=<tv-wifi-mac> ./venv/bin/python pair.py <tv-ip>

# 3. serve
./venv/bin/python vidaa_server.py <tv-ip> 8765

# 4. on the TV: browser -> http://<server-ip>:8765/ -> "+ INSTALL AS APP"
#    -> OK -> restart TV -> open "Home"
```

Harden `server/config.json` (hide preset apps, rename tiles, set `"autoSwitch": true` to auto-jump to a single active HDMI input on boot, or toggle the watcher) — it is read live. The launcher renders at 1080p (`?540p` fallback), caches tiles in `localStorage` for instant cold paint, auto-focuses active HDMI signals, and binds remote keys `1`–`9` as tile hotkeys. Production deployment on an always-on box:
[DEPLOY.md](docs/launcher/DEPLOY.md). Roadmap for shimming and modifying the native stock launcher (`/APPS/channelA/hisenseUI/`) directly on rooted TVs: [LAUNCHER_V2.md](docs/launcher/LAUNCHER_V2.md). One server per TV — the paired MQTT identity is exclusive.

## Quickstart — root

Root is **model- and firmware-specific**: the chain that works on a 50A51HUV
does nothing on a 100U7Q. Start at [docs/models/](docs/models/), match the model
*and* the firmware string exactly, and read that guide end to end before
touching anything. [SECURITY.md](SECURITY.md) has the disclosure stance.

The MTK9602 chain in one line: the browser bridge that installs the launcher can
be walked past its sandbox (`../`), the file API behind it is unauthenticated,
and a boot script executes a writable file as root — after that it is a static
dropbear and five hook versions. Full detail:
[the 50A51HUV guide](docs/models/50A51HUV/09.01O.P0813/README.md).

The recon probe ([launcher/recon.html](launcher/recon.html)) includes write
probes and a root hook installation action; inspect it before use. Installing
the hook changes your TV's boot behaviour.

## The docs

| Doc | What it is |
| --- | --- |
| [docs/](docs/README.md) | **The map** — every guide, finding and tool, with where to start |
| [docs/models/](docs/models/) | Model- and firmware-specific root guides — 50A51HUV, HE40, 100U7Q, 75UR9S, 43Q60SEVS |
| [EXPLOITS.md](docs/research/EXPLOITS.md) | Method inventory: tested devices, evidence, outcomes and limits |
| [AGENTS.md](AGENTS.md) | Briefing for AI sessions working in this repo |
| [TODO.md](TODO.md) | Open work, ordered — loose ends and the catalogue refactor plan |

## Repo layout

The repository root is the launcher product; the root research is filed by
model and firmware.

| Path | What |
| --- | --- |
| `launcher/`, `server/` | the launcher (the default, no-root lane) |
| `docs/models/<Model>/<FW>/` | per-model root guides, evidence and modding |
| `docs/research/` | cross-model inventory, method catalogue, tested-models guide, patched-firmware playbook |
| `docs/launcher/` | launcher deployment and v2 roadmap |
| `docs/project/` | story and the AI prompt ladder |
| `tools/` | scripts used by the guides |

## Tested models

<!-- INVENTORY:START -->
| Model | Region | SoC | VIDAA OS | Firmware | `transport_protocol` | Browser | Launcher | Root chain | Tested by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 50A51HUV | US/CAN | MTK9602 | U09.01 | 09.01O.P0813 | 3290 | Chromium 111 "odin" | working | achieved | [@carteakey](https://github.com/carteakey) |
| MTK9618 unit | ? | MTK9618 | ? | 09.60X.Q0609 (2026-06) | ? | ? | untested | achieved | [u/possibly_matt](https://reddit.com/user/possibly_matt) |
| 55A60LEVS | EU_A | MTK9603 | 9.0 | 09.60V.Q0612 (2026-07 EU_A) | 3290 | Chromium 111.5563.5.1 | untested | blocked-at-fileWrite | [u/Affectionate-End-601](https://reddit.com/user/Affectionate-End-601) |
| 43A60LEVS | EU | MTK9603 | 9.0 | 09.60V.Q0612 (2026-07) | 3290 | Chromium 111 "Odin" (111.5563.x) | untested | untested | [u/Wing-Tsit-Chong](https://reddit.com/user/Wing-Tsit-Chong) |
| ? | ? | MTK9603 | 9.0 | 09.60V.Q0612 (build date unconfirmed) | ? | ? | untested | untested | [u/____dls](https://reddit.com/user/____dls) |
| 65U7H | India | MTK9900 | U6 (exact version after update unconfirmed) | V0000.06.29X.P0813 | 3160 | Chromium 88 Odin | untested | in progress | [u/pavanjadhaw](https://reddit.com/user/pavanjadhaw) |
| HE40E5600FFWTS | ? (EU, German-language docs) | MT53xx / MT5863 class (armv7 Cortex-A53) | pre-9 (Linux 3.18.25, glibc 2.18, BusyBox 1.18.5, sysvinit) | V0100.01.00A.N0410 | untested (vector did not use MQTT) | hisenseUI (Chromium 59.0.3071.115, opera4x) + hisense_browser (separate process, DevTools 9224, --disable-web-security) | custom-UI templates shipped (start-UI.sh + /3rd_rw/UI/index.html, PIXI); not verified end-to-end | achieved (root + key-only SSH; boot persistence owner-verified across multiple reboots, 2026-11-04) | [@oOHiyoriOo](https://github.com/oOHiyoriOo) |
| 100U7Q (100U70QEVS) | EU_A | MT9655 (32-bit ARM userland) | U09.60 | V0000.09.60I.Q0813 | untested | untested | untested | achieved (SSH and PTY verified; manual re-trigger after reboot) | [@oOHiyoriOo](https://github.com/oOHiyoriOo) |
| 75UR9S | EU (Czech Republic) | MT9655 (32-bit ARM userland) | U09.0 | V0000.09.60W.Q0624 | untested | untested | untested | achieved (root + key-only SSH on 8008 verified 2026-11-04; boot persistence verified 2026-11-06 — re_sshd serviceList autostart re-arms dropbear at every cold boot) | [@EvzenP](https://github.com/EvzenP) |
| 43E7DS (43Q60SEVS_02, serial type 43E7SE) | EU_A (DEU) | MTK9603 | U09.60 | 09.60W.Q0612 (EU_A) | ? | Chromium 111 "odin" (multi-shell UAs: WebExplorer/1.2.8, SurfMaster/7.0.0, Weblayer, NetSurfer) | working | achieved (13 postinst runs as uid 0; no Dropbear on this build — boot persistence via the vendor service manager) | [@ryjr2ddznn-lab](https://github.com/ryjr2ddznn-lab) |
| 50A6Q (50A60QXVT) | UAE / intl (SSDP region 4) | NT72690 (Novatek; aarch64 kernel, armhf ELF32 userland) | U09.61 | V0000.09.61B.Q0721 | 3290 | Odin Chromium 111.5563.5.1 (aarch64) | untested | achieved (boot-persistent PFM/eval chain uid=0 + key-only SSH on 2222 verified 2026-11-06; self-healing re-plant loops) | [@aadnaane](https://github.com/aadnaane) |
<!-- INVENTORY:END -->

**Report yours by PR, not issue** — add a firmware entry to [inventory.json](docs/research/inventory.json) (single source of truth; fields and where to find them: [TESTED-MODELS.md](docs/research/TESTED-MODELS.md)) and run `scripts/gen-inventory.py` — every table in the repo regenerates from it.

## Contributors

<p class="contrib">
<a href="https://github.com/carteakey" title="carteakey — the project, 50A51HUV / MTK9602"><img src="https://github.com/carteakey.png?size=96" width="56" height="56" alt="carteakey"></a>
<a href="https://github.com/oOHiyoriOo" title="oOHiyoriOo — HE40 and 100U7Q guides and tooling"><img src="https://github.com/oOHiyoriOo.png?size=96" width="56" height="56" alt="oOHiyoriOo"></a>
<a href="https://github.com/EvzenP" title="EvzenP — 75UR9S / V0000.09.60W.Q0624"><img src="https://github.com/EvzenP.png?size=96" width="56" height="56" alt="EvzenP"></a>
<a href="https://github.com/ryjr2ddznn-lab" title="ryjr2ddznn-lab — 43E7DS / 43Q60SEVS, MTK9603"><img src="https://github.com/ryjr2ddznn-lab.png?size=96" width="56" height="56" alt="ryjr2ddznn-lab"></a>
</p>

Community reports: [u/pavanjadhaw](https://reddit.com/user/pavanjadhaw) ·
[u/possibly_matt](https://reddit.com/user/possibly_matt) ·
[u/LulzTigre](https://reddit.com/user/LulzTigre) ·
u/Affectionate-End-601 · u/Wing-Tsit-Chong · u/____dls · u/uzueta

A report without a model and firmware string stays in
[TESTED-MODELS.md](docs/research/TESTED-MODELS.md) until someone fills in the
gaps; that is the entry bar, not a judgement on the report.

### Finding your way around

The repo is growing faster than its layout, so start from the index rather
than the tree:

- [docs/models/](docs/models/) — one page per **model and** firmware string. If your model is not listed there, it is not documented yet.
- [EXPLOITS.md](docs/research/EXPLOITS.md) — every method, its evidence grade, and what already failed.
- [inventory.json](docs/research/inventory.json) — the single source for every table in the repo. Edit the JSON; never the tables.
- [AGENTS.md](AGENTS.md) — the briefing, including for an AI session doing the work.

Prior art and the safety stance are in [Credits & safety](#credits--safety) below.

## Credits & safety

Built on the shoulders of [Bananamafia's hisensehax](https://bananamafia.dev/post/hisensehax/),
[d3nd3/Hisense-mqtt-keyfiles](https://github.com/d3nd3/Hisense-mqtt-keyfiles),
[Krazy998/mqtt-hisensetv](https://github.com/Krazy998/mqtt-hisensetv),
[stevene1919/hisense_vidaa](https://github.com/stevene1919/hisense_vidaa) and
[Zfinix/vidaa-launcher](https://github.com/Zfinix/vidaa-launcher) (mechanism
reference only — this is an independent implementation).

No system partitions were written during this research; verified boot stayed
locked and green. Changes were designed to be reversible, but a complete
teardown has not been verified: it also requires restoring any edited UI files
and removing the root hook and its associated tools and configuration. The certificates and tokens in
`server/keys/` are device credentials — never commit them. Disclosure
status and reasoning: [SECURITY.md](SECURITY.md).
