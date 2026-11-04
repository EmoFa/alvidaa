# alvidaa

Two projects in one repo, one weekend, one TV:

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
that worked is in [docs/HACK-YOUR-OWN.md](docs/HACK-YOUR-OWN.md).

## The two lanes

```
LANE 1 — the launcher (no root needed)

┌─────────────┐   WebSocket    ┌──────────────────┐   MQTT/TLS 36669   ┌─────────┐
│ TV browser  │ ◄────────────► │ server (Pi)      │ ◄────────────────► │ VIDAA   │
│ canvas page │  JSON pushes   │ config + watcher │  RemoteNow control │ TV      │
└─────────────┘                └──────────────────┘                    └─────────┘

LANE 2 — the root chain (see docs/ROOT.md)

cert-gated MQTT ─► browser file bridge ─► ../ escape ─► unauth local API
    ─► rc.local boot hook ─► root at every boot ─► key-only SSH
```

Lane 1 has been tested on the model below; compatibility with other models
and firmware remains to be established. Lane 2 is **model-specific** (SoC and
partition layout bite there) and is documented
stage by stage in [docs/ROOT.md](docs/ROOT.md).

## Quickstart — the launcher

```sh
# 1. the 2024 client cert (the full story: docs/findings/01-mqtt-bridge.md)
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
[docs/DEPLOY.md](docs/DEPLOY.md). Roadmap for shimming and modifying the native stock launcher (`/APPS/channelA/hisenseUI/`) directly on rooted TVs: [docs/LAUNCHER_V2.md](docs/LAUNCHER_V2.md). One server per TV — the paired MQTT identity is exclusive.

## Quickstart — root

Read [docs/ROOT.md](docs/ROOT.md) end to end first, and
[SECURITY.md](SECURITY.md) for the disclosure stance. The short version:
the same browser bridge that installs the launcher can be walked past its
sandbox (`../`), the raw file API behind it is unauthenticated, and a
production boot script executes a writable file as root — after that it's
a static dropbear and five lockpick hook versions. The recon probe
([launcher/recon.html](launcher/recon.html)) includes write probes and a root
hook installation action; inspect it before use. Installing the hook changes
your TV's boot behavior.

## The docs

| Doc | What it is |
| --- | --- |
| [docs/ROOT.md](docs/ROOT.md) | **The root chain, stage by stage** — start here for lane 2 |
| [docs/findings/](docs/findings/) | The lab notebook, split into twelve modules (MQTT auth wall → Cobalt runtime & overlay traps) |
| [docs/EXPLOITS.md](docs/EXPLOITS.md) | Method inventory: tested devices, evidence, outcomes and limits |
| [docs/HACK-YOUR-OWN.md](docs/HACK-YOUR-OWN.md) | The staged prompt ladder for running this with your own AI agent |
| [docs/LAUNCHER_V2.md](docs/LAUNCHER_V2.md) | The on-TV launcher port plan (root-era roadmap, R0–R6) |
| [docs/DOOM.md](docs/DOOM.md) | DOOM at 1080p on the TV's framebuffer — the full recipe |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Pi deployment, single-instance rule, cutover notes |
| [docs/TESTED-MODELS.md](docs/TESTED-MODELS.md) | How to report your TV (fields, where to find them) |
| [docs/STORY.md](docs/STORY.md) | The whole story, full detail — the human version of the findings |
| [AGENTS.md](AGENTS.md) | Briefing for AI sessions working in this repo |
| [SECURITY.md](SECURITY.md) | Disclosure status and reasoning |

## Tested models

<!-- INVENTORY:START -->
| Model | Region | SoC | VIDAA OS | Firmware | `transport_protocol` | Browser | Launcher | Root chain | Tested by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 50A51HUV | US/CAN | MTK9602 | U09.01 | 09.01O.P0813 | 3290 | Chromium 111 "odin" | working | achieved | @carteakey |
| ? (MTK9618 unit) | ? | MTK9618 | ? | 09.60X.Q0609 (2026-06) | ? | ? | untested | achieved | @possibly_matt |
| 55A60LEVS | EU_A | MTK9603 | 9.0 | 09.60V.Q0612 (2026-07 EU_A) | 3290 | Chromium 111.5563.5.1 | untested | blocked-at-fileWrite | @Affectionate-End-601 |
| 43A60LEVS | EU | MTK9603 | 9.0 | 09.60V.Q0612 (2026-07) | 3290 | Chromium 111 "Odin" (111.5563.x) | untested | untested | @Wing-Tsit-Chong |
| ? | ? | MTK9603 | 9.0 | 09.60V.Q0612 (build date unconfirmed) | ? | ? | untested | untested | @____dls |
| 65U7H | India | MTK9900 | U6 (exact version after update unconfirmed) | V0000.06.29X.P0813 | 3160 | Chromium 88 Odin | untested | in progress | @pavanjadhaw |
| HE40E5600FFWTS | ? (EU, German-language docs) | MTK5863-class (MT53xx, armv7 Cortex-A53) | pre-9 (Linux 3.18.25, glibc 2.18, BusyBox 1.18.5, sysvinit) | V0100.01.00A.N0410 | untested (vector did not use MQTT) | hisenseUI (Chromium 59.0.3071.115/V8 5.9, opera4x) + hisense_browser (separate process, DevTools 9224, --disable-web-security) | custom-UI templates shipped (start-UI.sh + /3rd_rw/UI/index.html, PIXI) | achieved (boot persistence verified across multiple reboots) | @xXLucyNyuXx (angryzero/hisense-root) |
| 100U7Q (100U70QEVS) | EU_A | MT9655 (32-bit ARM userland) | U09.60 | V0000.09.60I.Q0813 | untested | untested | untested | achieved (SSH and PTY verified; manual re-trigger after reboot) | @xXLucyNyuXx (angryzero/vidaa) |
| 43E7DS | EU (DE) | ? | ? | 09.60W.Q0612 | ? | ? | blocked | untested | @ryjr2ddznn-lab |
<!-- INVENTORY:END -->

**Report yours by PR, not issue** — add a firmware entry to [docs/inventory.json](docs/inventory.json) (single source of truth; fields and where to find them: [docs/TESTED-MODELS.md](docs/TESTED-MODELS.md)) and run `scripts/gen-inventory.py` — every table in the repo regenerates from it.

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
