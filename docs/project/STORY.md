# alvidaa: the full story of taking my TV back

*Draft 2 — full detail. A build log turned blog post; everything technical has its canonical record in [FINDINGS.md](../models/50A51HUV/09.01O.P0813/FINDINGS.md) and the two-day commit history. Photo slots marked [📷].*

> "bruv. that is insane. … dump the firmware then mod it remove ads fix the
> launcher to be native … check what sort of telemetry games they are up to
> i am getting excited about owning this hardware finally."
> — me, hour six, to an AI session that had just handed me root on my own TV

---

## The problem

Every time I turned on my Hisense VIDAA TV, it showed me *its* home screen:
sponsored tiles, an app store I never opened, "content" recommendations for
services I don't pay for. The TV doubles as KPC's 4K60 monitor, so this
billboard stood between me and the PlayStation every single time. I don't
want a smart TV. I want a *dumb* TV: a clock, my HDMI inputs, my actual
apps, nothing else.

[📷 PHOTO 1: the stock VIDAA home screen — sponsored tiles and all, the "before" shot]

There were two screens to fix, actually. The living room also has a Fire TV
Stick, which is its own ad-delivery ecosystem. So on **Oct 27** I opened a
working session with a modest brief: *"i want to debloat dumb both
firestick and vidaa tv together."* I'd done a partial Fire TV pass back in
October (8 diagnostic/ad packages disabled over ADB), and my homelab docs
had a folder of saved writeups: the humblemuzzu "dumbtv" guide, a smart-TV
debloat guide, "Haxxoring a Hisense Smart TV," "I gave my Hisense TV a new
home screen," and a reference to someone's VIDAA launcher.

The plan that came out of reading all of it (`tv/DEBLOAT_PLAN.md`) had a
shape I ended up following for three days: Fire TV Stick via ADB first
(boring, documented, reversible), then the VIDAA TV — which the plan
initially called "settings hardening plus DNS blocking," because **VIDAA
isn't Android. No ADB. No developer mode.** The community root knowledge
all dates to pre-2021 firmware.

But the saved clippings contained one heretical fact: people *had* gotten
custom home screens onto VIDAA TVs. A project called `vidaa-launcher` did
it over the TV's own **RemoteNow** channel — the same MQTT/TLS channel the
official phone remote app uses.

My first instinct: just run it. Second thought:

> "we dont wanna copy it … will implement a version similar to dumbtv of
> our own … just reference"

So the plan got rewritten that evening: our own Fire TV debloat toolkit,
our own VIDAA launcher — reference projects read as documentation, nothing
run or copied wholesale. And a design constraint that stuck for everything
after: **"i dont want fancy launchers i want functional ones."** Functional
over fancy. Clock, apps, inputs. A launcher that can't be enshittified
because it has no feed to enshittify.

The architecture fell out of the hardware's constraints and got locked in
while we were still two days from a working build:

- The TV side is **one canvas page, stateless** — all config and state
  pushed by a server. VIDAA's browser couldn't composite normal HTML/CSS
  (at the time we believed Chrome 77; more on that later), so you draw
  everything, repaint cheaply.
- **WebSocket, not request/response**, between page and server — so
  "server offline" degrades gracefully instead of mysteriously lagging.
- **v1 scope: clock, apps row, inputs row — stop there.** Inputs were the
  part no generic launcher could do (KPC's tile live-status).
- Host it on the always-on Raspberry Pi, not a Mac — the reference
  launcher's author famously had his launcher die every time his Mac
  slept. We knew that failure mode before we wrote line one.
- Accept the ~1 second of stock home on the HOME button. VIDAA has no
  default-launcher setting; a watcher relaunching ours is the ceiling
  without root. (Narrator: there would be root.)

One more piece of advice from that planning night worth keeping: the Fire
TV launcher and the VIDAA launcher are architecturally different animals
(a real Android APK with the HOME intent vs. a web page plus a server
bridge), and trying to unify them would be "architecture tourism." Shared
visual language, separate codebases. And name them as a pair —
"dumbhome-firetv" / "dumbhome-vidaa" — so the systemd units read nicely.
(The VIDAA one escaped the naming scheme entirely within two days. It
became alvidaa.)

---

## Day 1 — the Fire TV Stick (Oct 27)

The Fire TV half of day one went the way the guides promise, which was
almost suspicious after what the VIDAA half would become.

**The pairing saga.** The stick (an AFTKRT on Fire OS 8.1, `<firetv-ip>`)
was reachable and ADB debugging was on — but the "Allow USB debugging?"
dialog refused to render for this Mac, a new ADB host. Roughly *ten
minutes* of continuous knocking, three polling rounds, an ADB server
restart, a stick power-cycle, and a full software restart later, the
dialog finally appeared… and I cancelled it by mistake. One more cycle and
it stuck. (The final trick in the escalation ladder, unused: pairing
wirelessly by 6-digit code, which bypasses the wedged dialog entirely.)

[📷 PHOTO 2: the Fire TV "Allow USB debugging?" dialog — or the ladder of terminal retries that earned it]

**Preflight read like a horror story.** 294 enabled packages, 9 already
disabled (my October work plus one pre-existing). NordVPN installed on the
stick — which settled a plan question: no on-device DNS filter, that would
fight the VPN; AdGuard Home on the Pi would do that job network-side.
Better than guessing from package names, we checked what was *running
right now*, and the ad stack had a body count in RAM:

| Package | State | RAM | Role |
|---|---|---|---|
| `com.amazon.tv.ftvambient` | running | 90 MB | ambient screensaver |
| `com.amazon.prism.android.service` | running | 73 MB | analytics/recommendations |
| `com.amazon.systemnotices` | running | 34 MB | notice popups/nags |
| `com.amazon.neo.minerva` (+logcat twin) | running | ~6.5 MB | logging |
| `com.amazon.device.telemetry.emitter` | running | 2 MB | telemetry upload |

**The sign-off and the kill.** I approved three batches plus the games
packages, keeping the ambient screensaver (I like it) and the camera-wall
viewer. Fourteen packages disabled, journaled, every step reversible with
a session-scoped rollback. Two bugs in our own toolkit surfaced mid-run
(an `adb shell` inside a `while read` loop eating the candidates file as
its stdin — classic) and got fixed on the spot.

**The stubborn survivor.** `com.amazon.ftvads.deeplinking` *refused* the
disable — it's one of Amazon's protected packages nobody can disable by
ADB. That single refusal defined the network phase later: DNS blocking is
the *only* counter for it, which made the AdGuard per-client rules
non-optional rather than nice-to-have. Three tiny Amazon logger processes
(~8.5 MB combined) also survived force-stop — sticky native services;
their packages are disabled so they can't do much, and DNS covers the
rest. Total after day one: **23 packages disabled** (9 pre-existing + 14
new), settings pass applied (`limit_ad_tracking=1`, animations at 0.5×),
plus two privacy toggles for me to flip by hand on the remote.

Both toolkits were scaffolded that night, the wiki got a Hisense page, and
the day ended with the Pi unreachable (foreshadowing), the Fire TV done,
and the VIDAA launcher design locked.

---

## Day 3, morning — resurrection and fingerprinting (Oct 29)

Two days later, back at it. First discovery: the Pi had been rebuilt after
an SD-card failure — AdGuard Home gone, old SSH keys dead. Recovery went
Mac → KPC (woken by Wake-on-LAN, since the Pi normally does that job) →
Pi, and a fresh dedicated key (`pi-ts`) made the Mac→Pi path direct from
then on. AdGuard's reinstall became my side quest; the launcher became
the main quest:

> "Yes lets start wit h the launcher and i will setup adguard on the side"

The TV got fingerprinted properly: SSDP finds it as a DLNA MediaRenderer,
and the device descriptor leaks a gold mine — `mac=`, `region=`, `brand=his`,
`vidaa_support=1`, and crucially **`transport_protocol=3290`**, a number
that predicts which authentication generation the TV's MQTT broker speaks.
"Living Room TV," `<tv-ip>`, WiFi, RemoteNow listening on 36669.

The plan: the launcher is a web page installed through VIDAA's hidden
installer (`hisense://debug`), served by a small Python server that
bridges OK-presses to the TV over RemoteNow MQTT. From the reference
projects we took only mechanisms: topic layout, the 4-digit pairing flow,
the home-watcher idea (`statetype == "remote_launcher"` = stock home is
up, relaunch ours), the cert every open-source Hisense remote ships.

[📷 PHOTO 3: terminal with the SSDP discovery + descriptor fields]

---

## The 2024 wall

We pulled the classic 2018 RemoteNOW client cert (`CN=remoteclientmobile`,
valid to 2043 — the one every open-source Hisense remote uses), wrote the
server (`vidaa_server.py`, stdlib + paho-mqtt, hand-rolled WebSocket on
one port), wrote the pairing CLI (`pair.py`), wrote the first canvas page
— and knocked on the TV's door.

The TV answered with the popup every 2024+ VIDAA owner knows:

> *"Your TV mode is no longer compatible with the version of the app.
> Please try with the latest version."*

MQTT rc 5, Not authorized, at CONNECT. Every guide on the internet uses
those 2018 credentials. All of them are dead on this firmware.

**The Rosetta stone** turned out to be issue #6 on a half-abandoned repo
(`stevene1919/hisense_vidaa`), where someone with the exact same
`transport_protocol=3290` firmware class had cracked it: 2024+ firmware
checks the **client certificate's identity at the MQTT layer** — TLS
handshakes succeed with *any* cert, but the broker only accepts the cert
belonging to the *current official VIDAA Smart TV Android app*
(`CN=VidaaAppAndroidV01`, issued by `CN=RemoteCA`, valid 2024→2034).
That's why the popup appears per attempt instead of the TLS layer failing.

So: get the official app's keystore. The APK mirrors (APKPure, APKCombo)
hard-block automated downloads — Cloudflare loops, even for a driven
browser. The manual step landed where all good sideloads land:

> "airdroppped to downloads. good catch"

…well, Desktop, but who's counting. It was an `.apkm` bundle of v1.09.06,
*newer* than the version in the issue thread, and this build even ships
the keystore un-obfuscated: `res/raw/client_mobile_android.p12` (same
2565 bytes as the older obfuscated `res/El.p12`). `openssl pkcs12 -legacy`
(the legacy flag matters — RC2/3DES ciphers) later:

**`CN=VidaaAppAndroidV01`. Exactly the identity the TV demands.**

The cert alone still wasn't enough. The modern firmware also wants
*dynamic* per-connect credentials, and someone at Hisense clearly had fun
designing them:

- `client_id = "<MAC>$his$" + md5("<const>$" + mac)[:6] + "_vidaacommon_001"`
- `username = "his$" + (timestamp XOR 6239759785777146216)`
- `password = md5(timestamp + "$" + md5("his" + digitsum(timestamp) + "h!i@s#$v%i^d&a*a").upper()[:6]).upper()`

…and after the PIN exchange, the TV issues real long-lived credentials
(2-day access token, 30-day refresh token) so you pair **once**. Our
`pair.py` implements the handshake with a four-profile fallback cascade
for older firmware generations that use the same shape without the XOR
mask.

[📷 PHOTO 4: the pairing handshake working — MQTT session established with the 2024 cert]

---

## The PIN war

Then came my favorite bug of the whole project. The TV shows a 4-digit
pairing code on screen; type it in, you're paired. Simple. Except:

1. **Every re-trigger rotates the PIN.** And our pairing session was
   sending a keepalive that re-triggered the dialog every 10 seconds —
   meant to hold the dialog open, it instead guaranteed the code I read
   off the screen was already stale by the time I typed it. The TV's
   answer, `result:100, "illegal authNum!!"`, became a familiar friend.
2. **The TV was talking and we were deaf.** The log showed *zero inbound
   pushes* while dialogs visibly appeared TV-side. The reference finally
   explained it: this firmware **denies wildcard MQTT subscriptions** —
   SUBACK returns "Unspecified error" for `/remoteapp/mobile/…/#`, and a
   naive client publishes fine and hears nothing back, ever. You must
   subscribe to *exact* topics.
3. After fixing subscriptions, one more trap: the server's message filter
   silently dropped **list payloads** — `if not isinstance(payload, dict):
   return` — but `applist` and `sourcelist` are JSON *arrays*. Half the
   TV's traffic was being discarded by a single line.

The scoreboard: `7286`, `2088`, `3144`, `5735` — four codes dead, each
rotated out from under me by our own keepalive. Remove the rotation,
trigger *once*, wait, submit:

`9201` — **PAIRED.** Tokens captured to `tokens.json`. The bridge was
alive: app lists, source switching, key injection, TV state.

[📷 PHOTO 5: the TV showing a 4-digit pairing code — the fifth one, the good one]

---

## First light — and the door that wasn't there

With the bridge working, the last step was installing the page as an app.
The plan said: open the TV browser, type `hisense://debug`, use the hidden
installer.

> "hisense://debug doenst seem to open"

Closed on this firmware. That 2021-era hidden installer door is gone.
Pivot, fast: a modern project (`vidaa-edge`) installs web apps on current
VIDAA firmware, and reading its source simplified everything — it serves
**plain HTTP** (no cert tricks), and the TV browser exposes its install
bridge functions to *any page it opens*. No DNS override, no hidden URL.
The new plan made the launcher page **self-installing**: it detects the
bridge functions and shows a `＋ INSTALL AS APP` tile; the TV writes
itself into its own app registry (`websdk/Appinfo.json`) via
`HiUtils_createRequest("fileWrite", …)`.

(Two quick own-goals from the same hour: I typed the wrong server IP into
my own instructions — `.88` is a different machine, this Mac was `.38` —
and the SETUP tile rendered white-on-white. The TV photo told the whole
story: it rendered, clock and rows and everything, with an invisible tile
and a cursor.)

The cursor was actually finding #1 of the day: **the VIDAA browser D-pad
doesn't send keyboard events — it moves an on-screen pointer**, and OK
emits a *click*. The page now hit-tests clicks on canvas tiles *and*
listens for arrow keys, so it works in both input modes.

[📷 PHOTO 6: the launcher rendering in the TV browser — first light, with the pointer visible]

> "woah. i installed and it shows up and works. how can we make this the
> default app and there is so much t od now. a looks like all my apps
> that i deleted are now abck in hsinsese if we could delete them if you
> can and hdmi says no signal even in app mode it ask to install app the
> ui is basic it doesnt scroll to the right. lets branch this whole thing
> out as a separate repo the whole hacking process + installing and ui
> and what not into its own and document findings so far like the cert
> thing and what not. so so much work hahaa lets"

One restart later, **Home** appeared at the end of the TV's app list and
booted like a native app. The TV had installed its own replacement
launcher from a plain HTTP visit. (Yes — that also means *any* page the
TV browser opens can silently do this. Hold that thought; it becomes a
security theme.)

## alvidaa is born

The spin-out came with a name I'm still proud of:

> "haha repo name should be alvidaa get it?"

*Alvida* — goodbye. VIDAA. The repo moved out of the homelab repo as
`vidaa-home` and was renamed `alvidaa` within minutes (the installed app
entry deliberately keeps its original `vidaa-home` Id — changing it would
install a duplicate). Alongside `server/` and `launcher/`, the third
commit created the project's real deliverable: **`docs/models/50A51HUV/09.01O.P0813/FINDINGS.md`**, a
lab notebook where every discovery gets written down the moment it
happens — the cert gate, the credential math, the exact-topic trap, the
PIN race, the install-API generations, the Chrome 77 constraints, the
pointer mode. "The doc that would have saved us two days."

Then the v1.1 bug-list sprint, driven by actually living with it:

- **"the old app keeps taking over"** — two bugs conspiring. The home
  watcher read TV state *passively*, but this firmware doesn't push state
  spontaneously enough, so pressing HOME just… stayed on the stock home.
  And the TV now had *two* "Home" entries (one pointing at the Mac from
  the first install, one at the Pi), and anything launching by *name*
  grabbed the stale one — which, during the cutover, flung me into a dead
  URL every time I tried to reach the browser to fix it. Fixes: the
  watcher **actively polls** `gettvstate` every 3 seconds, launches by
  **matching the app entry's URL against the server's own port** instead
  of name-first, and the self-install **purges stale duplicates** from
  `Appinfo.json`.
- **"hdmi says no signal"** — the TV exposes two flags, `is_signal` (0
  for every non-active input, which the old code trusted) and
  `has_signal` (actual presence). OR them.
- **"all my apps that i deleted are now back"** — preset apps can't be
  truly deleted via known APIs, so `config.json` hides and renames tiles
  instead. Read live, no restart.
- **"it doesnt scroll to the right"** — rows page in a 5-tile window
  with `‹ n / n ›` overflow indicators.

## The Pi deploy — 24/7 at last

Port 8765 on the Pi turned out to be taken — by the CasaKey camera-wall
service (`window-cam.service`). Not touching that: **alvidaa moved to
8770**, got a systemd unit (`Restart=always`), and the Mac dev server was
shut down (the paired MQTT client identity is shared — *one* server per
TV, or they kick each other off the broker; documented, then personally
rediscovered twice). Re-pointing the installed app meant one browser
visit to the Pi's URL and a reinstall — same app Id, overwrites itself —
plus a TV restart. An access log went in so the Pi's journal could prove
the TV was asking for the right host. It was: `host=<pi-ip>:8770`.

[📷 PHOTO 7: the Raspberry Pi running alvidaa.service, with the journal showing the TV's requests]

## v1.2 → v1.3 — the polish layer

- **Real app logos.** The applist payload turned out to carry CDN URLs
  (`img.vidaahub.com`) for every app's icon, hidden behind a weird
  `data:image/png;base64,iconDownload` prefix. The server extracts,
  proxies, and disk-caches them — one origin, survives CDN hiccups.
  Animated focus (requestAnimationFrame, only while animating — the
  TV's GPU barely notices), gradient background drawn per-frame (full-screen
  offscreen canvases render *empty* on this TV), signal dots on inputs.
- **The "server offline" flag that wasn't the network.** The TV's
  WebSocket died exactly 1.0s after connect, every time. Root cause: a
  0.5s socket timeout set for idle-waiting *poisons* Python's buffered
  reader once it fires — the next read raises, the handler exits. It had
  been silently degrading since v1.0. Fixed with `select()`.
- **The allowlist.** `config.json` got an `"only"` list — Live TV,
  YouTube, Spotify, (soon) Browser — and the SETUP tile hides itself once
  installed (`?setup` is the escape hatch to get it back). Comedy beat:
  the `"only"` handler was silently missing from the config loader, so
  the allowlist did nothing until a probe caught it. Every bug gets a
  FINDINGS entry; some get an apology.
- **Wallpapers.** Three generated abstract backgrounds rotating by day —
  first version nearly black under a 55% dark overlay, i.e. invisible;
  brightened palette + 35% overlay after the TV panel ate them.
- **Live signal pushes** (~9s re-query) so input dots flip green when
  KPC wakes; **input glyphs** so HDMI tiles can say "PlayStation 5 🎮"
  instead of "no signal". The one honest *no* of the project: live
  thumbnails of what's playing on each HDMI input — no VIDAA API exposes
  other inputs' video; that's the TV's internal pipeline.
- An hourly **AdGuard automation** got armed in the background: ping the
  Pi's AdGuard on 53/80, and the moment my reinstall lands, tee up the
  per-client DNS rules (Perflyst SmartTV list → TV, Fire TV list → stick,
  SessionReplay → both) without me having to remember.

[📷 PHOTO 8: launcher v1.3 — real logos, wallpaper, signal dots, the 5-tile row]

**Meanwhile, the side quest.** That night AdGuard Home came back up on the
rebuilt Pi, and the hourly check armed earlier that evening fired within
the hour: all three blocklists verified reachable (291 + 70 + 24 rules —
the Smart TV list, the Fire TV list, and the session-replay list). One
snag: the secret-manager CLI that would have let the automation wire up
the per-client rules itself had vanished from KPC in the meantime, so the
last two minutes — create the two clients (TV `.12`, stick `.82`), assign
each its blocklist — landed back in my lap as a dashboard visit. The
outer telemetry layer is one login away; the DNS sinkhole it feeds
(`ftvads.deeplinking`'s only counter) is already up.

---

## "Check online for firmware gaps"

Which brings us to the evening of the same day, and the message that
turned a launcher project into a root project:

> "clone reverse engineering eanything repo look online if firmware hacks
> exist for vidaa os and see if you can come up with a backdoor to gain
> root access to my tv"

The `rea` repo ("Reverse Engineer Anything") is an MCP toolkit that wires
an agent into Hopper/Ghidra/IDA/Frida — cloned and staged for the binary
work we assumed was coming. The literature review, done properly:

- **[Bananamafia's hisensehax](https://bananamafia.dev/post/hisensehax/)**
  (2021) is still the deepest writeup — and it *never achieved root*.
  Arbitrary file reads in HTML5-app context, silent app installs, a
  hardcoded serial-console password hint, busybox stripped of
  `telnetd`/`ftpd`, and a persistence idea considered and abandoned as
  too brick-adjacent.
- **[XDA's 2025 MT9618 guide](https://xdaforums.com/t/root-guide-android-tv-how-to-root-mt9618-hisense-tvs-using-mainboard-part-rsag7-820-13493-65u8n-55u8n-etc.4744258)**
  shows the hardware path alive on newer boards: service menu → enable
  UART console → USB-TTL adapter.
- **[giofrida's Hisense-Smart-TV-Enhancements](https://github.com/giofrida/Hisense-Smart-TV-Enhancements)**
  proved (older models) that a user-writable partition feeds code the TV's
  own UI loads — the concept that writable-code-execution exists on this
  platform.
- A **VIDAA 9 writeup** uses exactly our `Appinfo.json` trick — but never
  pushed past `websdk/`. Another project's issue reports the bridge being
  restricted on some firmware generations. Ours demonstrably still had it.

**Conclusion: no public root method for 2024+ VIDAA exists.** But we were
not starting from zero — we already had something nobody had publicly
pushed past its intended use: the `HiUtils` file bridge, running inside
the TV's browser. The gap was ours to fill, and the plan became a ladder
where each rung only depends on what the previous rung reveals.

## The ladder: recon v1 → v8

The instrument was `launcher/recon.html` — a self-reporting probe page.
Each version loads on the TV (increasingly *remotely* — more soon),
runs its probes, and POSTs everything to a `/api/recon` endpoint on the
Pi, which snapshots it as `recon-report-vN.json`. One version, one
question. And a running joke of the whole ladder: the Pi deployment
turned out to already exist (`alvidaa.service`, enabled, port 8770 —
synced and restarted from the launcher session's work), so v1's report
was *already waiting* when we went looking — I had opened the page on the
TV seconds after the endpoint went live, before anyone asked me to.

**v1 — what's there?** The bridge surface: ~85 `Hisense_*` functions plus
`HiUtils_createRequest`, enumerable with `Object.getOwnPropertyNames(window)`.
The user-agent says **Chromium 111, Linux armv7l, 32-bit** — the "Chrome
77" from every writeup, including our own FINDINGS, is stale on this
firmware (the recon pages still ship ES2018 out of habit). And the wall:
`fileRead`/`fileWrite` are sandboxed to the `websdk/` base; every absolute
path refused; `file://` XHR blocked in browser context.

**v2 — can we get out?** Yes, and the exit was beautiful: a *failed*
absolute read leaks its errno, the errno leaks the sandbox base —
`open("/APPS//etc/passwd") → ENOENT` — and `../` walks straight out to
the real root. `../proc/mounts`, `../etc/passwd` all read; a traversal
**write** to `../tmp/` succeeded and read back. Arbitrary read+write as
the bridge's uid, filesystem-wide. Identity calls pinned the hardware:
MediaTek **MTK9602** (not the HiSilicon everyone documented!), model
`50A51HUV`, firmware `V0000.09.01O.P0813`, browser codename "odin".
The mounts revealed the shape of the cage: rootfs is **squashfs, read-only,
dm-verity protected, verified boot locked/green** — system partitions are
a permanent no-fly zone — but `/APPS`, `/data`, `/var/local`,
`/var/tvservice`, and `/OAD` (the OTA staging partition!) are read-write.
And `/etc/passwd` had two fascinating lines: root's shell is *a script*,
and there's a **UID-0 account `cli`**.

**v3 — who's listening?** The UART console is **live** (`inittab` respawns
`getty -L ttyS0 115200` — a USB-TTL adapter on the service port reaches a
real login prompt, gated only by a script). And the accidental discovery
of the day: a probe failed with `NetworkError: … localhost:9009` — the
bridge is just JS shims doing XHR to an **HTTP service on the TV itself
at `localhost:9009`**. Two consequences: we can talk to that service
directly and fuzz its full action surface; and binary reads **crash the
backend** mid-run (`../bin/sh` took the whole report down with it —
reproduced twice), so recon pages now POST their report *incrementally,
after every section*.

**v4 — what is the bridge?** Patching `XMLHttpRequest.prototype` captured
the exact wire format: `POST {"api":"fileRead","args":{…}}` with a
rotating `identifier` header. `/proc/self/cmdline` + `/proc/self/status`
unmasked everything: the backend is **"phoenix," a Node.js server**
(`/opt/pkgs/tv.vidaa.app.phoenix/bin/phoenix`) running
`/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/phoenix.server.js` as **uid 314**
(`UhisPhoenix`) — no capabilities, no seccomp, SELinux **permissive**
(the boot script literally calls `setenforce 0`). The file bridge's own
source code sits on the partition we can write.

**v5 — what does the raw API allow?** The raw API works **with no
identifier header at all**, and answers `Access-Control-Allow-Origin: *`.
Any page the TV browser ever opens has the whole filesystem as uid 314.
(Third time this theme appears: the TV browser must never see the open
web.) Fuzzing 17 action names returned a uniform clean
`"Not supported api"` — a perfect oracle, but no exec-class API exists in
the guessable namespace. And `start-hisense.sh`, the root-run master
service starter, contained the first root-lane candidate: a trigger file
on `/APPS` we can write (`NewUpdatedIPK.txt`) that launches
`set_ipk_path.sh` as root.

**v6 — which boot script is the one?** `set_ipk_path.sh` turned out to be
a symlink flipper (A/B `CHA`/`CHB` package scheme), not an installer — a
lane, not a door. `deploy_oem_data.sh` was more interesting: a **root-run
arbitrary file deployer** that copies everything under
`/var/local/oem/…` — and `start-hisense.sh` does `chmod 777 /var/local`
at boot, i.e. the bridge can write it — into protected partitions,
remounting `/vendor/tvconfig/config` rw itself. But the white-name map of
legitimate destinations would turn out to be data-only. And phoenix's own
environment (readable via `/proc/self/environ`, since fileRead runs *as*
phoenix) named a second JS service package where the real action table
lives.

**v7 — how does the console gate work, and is there a door?** The UART
root shell gate (`key_check.sh`) got fully reverse-engineered: a FAT32
USB key whose file must be named `md5(vendorID + productID + tvModel)`,
content validated by a binary, with an interactive `dummy` fallback —
and `/tmp`, where key files are looked up, is a tmpfs the bridge can
write. Placement trivial, content check the only gate. But then the
real door, found in `rc.local` (run as **root** at every boot):

```sh
if [ -e /var/local/otaTest.sh ]; then
    chmod +x /var/local/otaTest.sh
    /var/local/otaTest.sh &
fi
```

`/var/local` is the rw partition the bridge owns. **Writing that one file
= arbitrary code as root at next boot.** An OTA auto-test hook left armed
in production firmware. No symlinks, no config parsing, no crypto.

**v8 — arm it.** The recon page grew a red **INSTALL ROOT HOOK** button
(writes the hook with a guard against overwriting a foreign script, and
the hook self-documents its removal), plus a `hookinstall.html` page so
the hook can be re-installed *remotely* — and a `hookcheck.html` that
verifies what's on disk — both pushed to the TV over the MQTT session,
zero physical contact. The hook, at next boot, as root: dumps
`id`/`ps`/listening ports, copies the root-only files (`/etc/shadow`,
the gate scripts, the `check_usb_key` binary) into world-readable
`/var/local/rootdumps/` so the bridge can read them back, and starts
`busybox telnetd` on 2323.

[📷 PHOTO 9: the recon page on the TV with the INSTALL ROOT HOOK button — or the recon report JSON on the Pi]

**The remote control trick.** Somewhere in the v8 era, typing URLs on a
TV remote became obsolete too: the server gained a one-line `/api/open`
endpoint that publishes `launchapp` with an **arbitrary `http` URL**
through the existing MQTT session. Any page, loaded on the TV, from the
couch. (Finding along the way: the broker allows **one session per
credential set** — a second client with the same username/password dies
even with a different client_id, so everything publishes through the Pi's
one healthy connection. Also: the firmware disables ICMP echo, so every
"ping the TV" check in the world silently lies; TCP 36669 is the honest
probe.)

---

## The plug pull

We armed the hook and rebooted the TV. Nothing. The report came back and
`/proc/uptime` said **26.6 hours** — the "reboot" had been a standby
round-trip, and standby never re-runs `rc.local`. Some lessons still
require physically unplugging the television.

> "holy shit i ran it rebooting now."
> … "ok tv should be up."
> … (uptime: 95,735 seconds and counting)
> — "The hook is armed but the TV never rebooted. **Pull the wall plug for
> 30 seconds.**"

Thirty seconds of darkness later, the smoking gun: uptime **250 seconds**,
and `/var/local/otaTest.log` **exists but is unreadable** — root-owned
640, because the hook chmod'd its dumps to world-readable but forgot its
own log. Failure-as-evidence: the file could only exist if the script
ran, and it could only be denied if the script ran *as root*.

**ROOT: CONFIRMED.** The harvest, read back through the bridge:

- **`/etc/shadow`** — root's SHA-512 hash; `television` and `cli` share
  one hash between them.
- **`rootlogin.sh` is a two-liner** (`source key_check.sh; main`) — the
  UART root shell *is* the USB-key gate, nothing more.
- **`cli_login.sh`** reveals Hisense's serial-debug crypto: an
  RSA-signed, AES-encrypted command package decrypted with keystore-wrapped
  key material — all of it root-only files, all of it now on the shopping
  list.
- Port 2323 stayed closed: this TV's busybox has **no `telnetd`**.

[📷 PHOTO 10: the wall plug, heroically unplugged — the highest-leverage thirty seconds of the project]

## Hook v2 and the toolbox

Hook v2 installed itself remotely (`hookinstall.html` pushed over MQTT
through `/api/open`; v1 backed up to `/var/local/otaTest.v1.bak` — the
installer keeps a single rolling backup slot, so the full lineage lives
in FINDINGS.md and the session log, not on the box), and fired on the
next real boot with uptime 46 seconds and an 18 KB master-key log. The
applet inventory said
no to `nc`, `wget`, `httpd`, `ftpget` too — but yes to `dd`, `tar`,
`gzip`, `mount`, `chroot`, `reboot` (remote reboots from now on; the plug
never comes out again), and, best of all, `/bin/sh` is **real bash**, and
bash has `/dev/tcp/host/port` built in: a raw TCP client with zero
binaries. That's the network primitive for everything — shell download,
firmware dump, reverse shell.

And `/usr/local/bin` is a treasure chest, inventoried in FINDINGS §10.12:
**`iptables`** (root firewall — the future home of ad/telemetry blocking,
in-kernel, persistent), **`opkg` + `ipk-decrypt`** (the legit package
channel), `openssl`, `7za`, `jq`, **`screenshot`**, `secure_exec`,
`superwatch` (the supervisor that had been resurrecting phoenix after our
crash tests all along) — and the telemetry stack, named and flagged for
the kill list: **`hi_logreport_service`, `mdharvester`, `write_stat`,
`bizm`**.

Hook v3 closed the shell gap: a static musl `busybox-armv7l` 1.31 (this
one *has* `telnetd`) staged on the Pi behind a raw TCP file server; the
hook waits for the network at boot, fetches it over bash `/dev/tcp`, and
starts a root listener. The TV now fetches its own shell from my Pi every
boot.

## SSH (the last mile)

Telnet was always just fastest-first-contact, and an unauthenticated root
shell open to the LAN is a loaded gun — any gadget on the WiFi gets root
on the TV. The proper endgame: **static dropbear, key-auth only**. The
firmware has no SSH binary anywhere, the read-only rootfs can't take
dynamic binaries, and there's no Docker on the Mac — but there *is*
**zig cc**, which cross-compiles `arm-linux-musleabihf` natively: a
static armv7 dropbear built straight on the Mac (one build gotcha for
FINDINGS: the bundled libtomcrypt archives must be made with zig's `ar`,
not the macOS host one). Better still, dropbear 2025.88 has a runtime
option for the authorized-keys directory, so the read-only-`/root`
problem solves itself (`-D /var/local/roothome`). Hook v4 shipped the
whole payload — busybox + dropbear, fetched at boot over bash `/dev/tcp`
from the Pi, with a retry loop (the first three fetches hit an
unconnected network; the fourth landed).

Then Hisense's last lock, and the best discovery of the night: **the TV
ships its own anti-tamper firewall.** INPUT jumps to a
`FIREWALL_IN_EULAON` chain whose policy is: allow MQTT 36669, ICMP,
loopback, one marked flow — **DROP everything else**, with an explicit
blacklist of debug ports: 22, 23, 4444, 9222 (Chrome devtools!), 12321.
Both daemons were alive the whole time; the firewall was silently eating
the SYNs — that's why SSH *timed out* instead of refusing. Hisense
anticipated exactly this class of attack and locked the debug ports down
at the kernel layer. Hook v5 (installed remotely, v4 preserved as
`.bak`) inserts accept rules for 2222/2323 at the top of INPUT —
re-applied in a loop for the first minutes of boot, so later boot stages
can't quietly reload the firewall around them.

After the next boot, dropbear answered — a real
`Permission denied (publickey)` from the daemon, not a timeout. And then
the gauntlet, one lock per hook version: `-D` *replaces* the `.ssh`
directory (key relocated to `/var/local/roothome/authorized_keys`, fixed
live over telnet); root's login shell is a custom script missing from
`/etc/shells` (v6 patches the check); and the beautiful one —
`start-hisense.sh` does `chmod 777 /var/local` at boot, so dropbear's
`checkpubkeyperms()` (which rejects keys under world-writable
directories) was doomed on every placement we control. v7 shipped a
binary-patched dropbear; v8 patches the perms walk itself ("the owner
decides where keys live"). zig's `objcopy` turned out to be broken for
the strip step, so the payload ships unstripped at 2 MB — fine.

And then the fifth lock, the funniest: the session finally
**connected** — and the output was literally `1`. That's `key_check.sh`'s
error code. Root's login shell on this TV *is* the USB-key gate script,
so a successful SSH login spawned the gate, which printed its failure
and quit. **The gate was wearing root's shell as a costume.** The right
fix was dropbear's per-key forced command (`command="/bin/sh"`) — and my
shell escaping mangled it into literal `\"`, producing the eerie "auth
OK, zero output." v10 deleted the forced command entirely (the patched
build execs `/bin/sh` directly) and started dumping the on-disk key file
+ binary md5 into the boot log — evidence, not theory. One process fix
learned the hard way along the way: you restarted the TV mid-push once
and the old payload won the race, so v10 always re-downloads its payload
at boot. And broken SSH configs now get validated on the Pi itself,
which happily runs the armv7 dropbear in 32-bit compat — no more
rebooting the TV to test a config line.

**SSH: IN.** `ssh -p 2222 -i server/keys/tv_root_ed25519 root@<tv-ip>`
lands at a root shell, key-only, from the laptop, at every boot. Five
locks, five hook versions (v5–v10), zero plug pulls since the root one.
The jailbreak is done.

## The first hour of ownership

What you actually do in the first sixty minutes of owning a TV you were
never supposed to administer:

```
uid=0(root) gid=0(root) groups=0(root)
Linux hisensetv-<ethernet-mac> 4.19.79+ #1 SMP PREEMPT Wed Aug 13 2025 armv7l
```

The hostname is the TV's ethernet MAC — it introduced itself. Kernel
4.19.79, built August 2025. 1.2 GB RAM. The `command not found` noise in
the first session is just dropbear's non-login PATH — cosmetic. A
ten-line wrapper in the repo (`server/tv`, run from the laptop) turned
the whole thing into one command from the couch: `server/tv` for an
interactive root shell, `server/tv 'cat /proc/mounts'` for one-shots.

**The inventory.** Full eMMC map, captured in the first sitting: 3.87 GB
eMMC, 42 partitions — `p20` the 36 MB verity-protected squashfs rootfs,
`p22`/`p23`/`p24` the app/vendor images, `p38`–`p42` the big read-write
data partitions (where `/APPS`, `/var/local`, and everything we've been
living in actually sit).

**The firmware lane, proven.** `dd` the verity-protected rootfs (p20)
straight to the Pi over `/dev/tcp`, mid-conversation: `hsqs` — SquashFS
4.0, LZO-compressed, 30.5 MB, built 2025-08-13. The TV's entire root
filesystem is now a file on a Raspberry Pi. Unpacked, it paid rent
immediately: `/etc/0001-cli-login-aes.pem` — the decrypt key for
Hisense's serial-debug CLI, sitting in the image at mode 444 (never
actually secret, just unreadable until you owned the read) — and the
missing `/etc/shells` that cost us a hook version confirmed by the
filesystem itself. Everything Hisense considered root-only is now a file
we own. Verified boot stays green and nothing was modified — we didn't
change the rootfs, we *read* it. Own the read, and the write matters
less.

**The journalist's tour.** By midnight even the second window — the one
writing the story — had the key. A read-only tour, three light batches:
`hostname` = `hisensetv-<ethernet-mac>` (the ethernet MAC); `/proc/cpuinfo`
says ARMv7 rev 4, `free` says 1.2 GB with 808 MB already used (the TV is
busy being a TV). `/var/local` is a city — the hook lineage on disk
(`otaTest.sh` v10 at 3.1 KB, `otaTest.v1.bak`, a 14.8 KB `otaTest.log`),
the OEM-deployer's own logs (`deploy_oem_process.txt`), and our static
busybox. `rootdumps/` reads like a heist inventory: `shadow` (639
bytes), `cli_login.sh`, `key_check.sh`, `rootlogin.sh` (all 56 bytes of
it), the `check_usb_key` binary, both CLI crypto keys. `cat /etc/shells`
→ `No such file or directory` — the lock that cost hook v6, confirmed by
the OS itself, live. The telemetry quartet on disk: `bizm`,
`hi_logreport_service`, `mdharvester`, `write_stat`. The firewall ledger
shows our 2222/2323 accept rules stacked in duplicate layers (the
re-apply loop's fingerprints — cosmetic, dedup is v11 material). And
`/APPS/channelA/{hisenseUI, operation-ui, system-ui}` — the stock home's
UI code on the writable partition: the ad-strip phase already has its
map. And the ad-strip verdict, from reading `deploy.sh` as root: the UI
is plain web code (`hisenseUI` 5.0 MB — index.html, process.env.json,
shared/static; operation-ui 19 MB; system-ui 53 MB) and normal boots
never touch it — the re-deploy path only fires when an OTA upgrade flag
exists (`/var/local/upgrade/upgradeversionflag`). Two caveats: an OTA
does `rm -rf` on the whole channel and re-extracts `hisenseUI.tar.gz`
from `/OAD` staging (so the ad-strip dies with any firmware update —
freeze OTA first, keep a tar on the Pi), and a boot script chowns the
channel back to `UhisApp:UGhisApp` + chmod 750 (edits must stay readable
by that user). Sequence: tar → canary edit → reboot → verify → strip.

**The archaeology (00:15).** The hacker's session went digging in
`/usr/local` and came up with the best plot twist of the night: this
"Hisense" firmware is built on **Loewe's chassis framework** — the
German premium TV maker. `dclkeys.cfg` is Loewe's DCL config format, the
chassis is "HL1", there's a `LoeweSl22x.dat` clone file, and `kilby`
ships per-brand service lists for **CVTE, Loewe, and Cultraview** — a
multi-brand ODM platform, with `huangdao.db` named after Hisense's
Qingdao campus. CVTE (the ODM) also left **factory logger scripts that
remount `/` and `/usr/local` read-write** — leftovers from the
production line — and the firewall's own source confirms it gets flushed
on EULA state changes, which retroactively validates the re-apply loop
in hook v5. The telemetry-endpoint hunt is underway: `deploy.sh` and the
27 MB `tvmain` binary, in for a strings sweep.

**R2 begins (00:18).** Meanwhile the launcher session got the keys too —
"The other session just handed me the keys, literally" — and immediately
did the right thing when it found its own half-applied hook edit from
the pre-SSH era: reverted it, zero remnants, to avoid colliding with the
other session's active hook work. Then straight into R2 (map the home
plumbing): the stock home is a **plain webpack SPA** — `index.html` is a
six-line loader pulling `app.js` chunks into `#app` — and
**`hisense_stage0.sh`** is the boot script that launches it. That's the
shim target for R5, being read right now. Two agents, one TV,
coordination notes in the repo, nobody stepping on anybody.

**The second tour (00:2x).** My own SSH dig, read-only, went deeper and
came back with the load-bearing facts:

- **The OTA re-deploy path is dormant right now** — no
  `/var/local/upgrade/upgradeversionflag` on disk, so direct UI edits
  would persist today.
- **The OTA switch is already off.** `/OAD/AppUpgradeSwitch.json`:
  `"country":"CAN","upgradeFlag":"0","resetFlag":"0"` — server-stamped
  with an md5, factory-reset switch also 0. Caveats: md5-integrity
  (naive edits get caught) and the OTA service likely rewrites it from
  the server — the iptables freeze stays the real R0, but the
  manufacturer has updates switched off at the switch level already.
- **The telemetry launcher is five lines**: `start-hislogreport.sh` runs
  `/usr/local/bin/hi_logreport_service &` if the binary is executable.
  One `chmod -x` from silence.
- **The sponsored content is network-fed** — the UI's `presetData/`
  holds one national-info file. iptables kills the data, the code strip
  kills the components; complements, not alternatives.
- **The DNS blocking has leaks**: `resolv.conf` = Pi (AdGuard) first,
  then 1.1.1.1 and three IPv6 resolvers as fallbacks. Closing those
  (iptables DNS redirect / router RA control) just moved up the list.
- `process.env.json` in the UI: `BRAND: HIS, AREA: NA, PLAT: 9602`,
  `REPORT: false` — a telemetry flag in the build snapshot, teasing.

**R0: the guardrails went in** (no hook churn — the boot hook already
sources `/var/local/tvrc`, so the rules appended there survive reboots):
the DNS bypass is closed in-kernel — all outbound 53/853 rejected except
AdGuard, verified live (`github.com` resolves through the Pi; `1.1.1.1`
now answers `Operation not permitted`) — and the OTA host is frozen
(`ota-tv.vidaahub.com` → 131.189.69.51, REJECT). Honest caveats filed:
`ip6tables` doesn't exist on this firmware, so the IPv6 fallback
resolvers are only mitigated by AdGuard being first in `resolv.conf`
(router-side RA control would finish the job), and the OTA block is an
IP rule on a rotating CDN — the DNS close is the durable layer. Unfreeze
is one deleted file's worth of lines and a reboot, by design.

**The wiretap got its salvager — and its first catch.** The LOG rules
write to the kernel ring buffer, and the TV's own kernel spam wraps it in
minutes; fourteen hours of wiretap had evaporated down to one line. A
two-minute background loop now mines `dmesg`, strips timestamps, and
keeps the unique endpoint set. The first haul, before the ring even
finished one wrap: **the TV phoning an Amazon S3 bucket over plaintext
HTTP, port 80, no TLS** (`16.182.75.50` — reverse-resolves to
`s3-us-east-1-r-w.amazonaws.com`), and DNS flowing through AdGuard only.
One oddity: a SYN to the Pi on port 5555 — ADB's port, on a TV that has
no ADB. Noted, unexplained.

**The caller got its name the same afternoon.** With every TV DNS query
flowing through AdGuard, the query log held the answer:
**`spectrum.s3.amazonaws.com`** — a telemetry-flavored bucket name if
ever there was one — queried at 16:23 UTC and answered with exactly that
S3 address. Now blocked for the TV client. The whole AdGuard layer
landed in the same pass: two per-client entries (TV + Fire Stick), the
Perflyst blocklists rule-tagged with `$client=` modifiers (AdGuard has
no per-blocklist client scoping in any version — verified in the source
before choosing the mechanism), the OTA freeze at DNS level
(`ota-tv.vidaahub.com`, durable where the kernel IP rule rotates), and
the full BLOCK tier from the endpoint map — recommend-ui, home-ui,
layout-ui, topic-ui, sport-vidaa, promovod — so the stock home's
recommendation tiles starve at the resolver. Scoping proven with a
`check_host` matrix; the TV was asleep, so the end-to-end dig is queued
for its next waking.

**The next two days were the consolidation.** The backup question got its
final answer: **42/42 partitions captured, byte-verified, mirrored on two
machines** — 943,718,400 bytes of p42 alone, rescued in chunks after
sustained reads at its tail hung the block layer hard enough to drop SSH.
The brick question is now closed at the strongest level available to
software: every read-write partition's exact prior state is restorable
file-by-file through the bridge.

The security analysis got teeth. The `euladpp` tar archives carried a
tar-slip lane that needed no `../` at all — and the verdict came back
"GNU tar 1.17 hardened both vectors," one for the disclosure file. The
bridge's full API table got decoded from its own source, including the
mode-list bases (`channelA`, `/OAD`, `/tmp`) — and then the
**security-code forge**: the successor to the "05328087" serial-console
era checks an HMAC-SHA1 whose inputs are all public (the MAC rides the
SSDP descriptor; `GetDeviceCode` returns a constant), and the forged code
was accepted live — `setDebugPort` flipped to the develop-devtool level.
The debug port stays firewalled; the decision is documented. That one
goes to Hisense.

And the blocking war got its second layer. The TV ships
**DNS-over-HTTPS evasion by design** — `/APPS/domain/domain_list.json`
declares `dns.google/dns-query` for vidaahub lookups, so a plain DNS
block was never going to hold. Countermeasure: REJECT 8.8.8.8/8.8.4.4:443
at the kernel, tiered kill-list artifacts built
(`firmware/adguard-blocklist.txt` + `firmware/tvfw`), and the
wiretap moved to a two-phase methodology — a baseline floor, then a
deliberate privacy-toggles-ON window via the `euladpp` switches, to
measure what "off" actually means. The patched-firmware playbook
(09.60V/MTK9603 lanes) and a machine-readable inventory went up for the
community rows. The harvest then got read —
1,153 lines collected, and the first window already told a story:
**447 DoH bootstrap attempts to 8.8.8.8** — the evasion firing
constantly, exactly as the countermeasure predicted. The kill-list went
live at both layers the same hour: `firmware/tvfw` at the kernel, and 17
TV-scoped rules in AdGuard (the tiered blocklist applied and
check_host-verified by the AdGuard agent; `ota-tv` resolving again at
DNS level by design, since the kernel now owns that block).

**And the TV left the LAN.** Tailscale (1.104.4, armv7) is on the
tailnet — `hisensetv-88b863c83aa5`, kernel 4.19.79, key-only SSH
reachable from anywhere, not just the couch. The admin console
screenshot went into the post with the tailnet IPs and emails blurred.

**And the repo went public.** README rebuilt around the truth (a
launcher and the first public root path for 2024+ VIDAA), the findings
split into nine modules, an agent-briefing file, a security-disclosure
document in preparation, the tested-models matrix waiting for other
people's TVs. "GitHub publish pending my courage" — the courage arrived
somewhere between the shotgun pickup and the wiretap.

[📷 PHOTO 11: the connected session printing `1` — the gate in root's shell costume — and then the `#` prompt]

## Of course we ran Doom

Every owned machine since 1993 owes the same tax, and this TV was
overdue. The ultimate root test isn't reading `/etc/shadow` — that only
proves you can *read*. Running Doom proves you *own*: a game from 1993,
cross-compiled for a chipset its engineers never imagined, drawing
straight into the framebuffer of a smart TV, through its own anti-debug
firewall, over SSH, from the couch.

The recipe:

- **doomgeneric** — a Doom port with a deliberately tiny porting
  surface: five functions (init, draw, sleep, ticks, get-key) and the
  whole engine comes along.
- A ~100-line framebuffer backend: open `/dev/fb0`, mmap, nearest-
  neighbor 320×200 → 1920×1080 every frame (the TV's fb is MStar FB0,
  32bpp, 1920×1080 with triple-buffered virtual height).
- Cross-compiled static-armv7 with the same `zig cc` toolchain that
  built dropbear (missing `main()` — every port carries its own; missing
  net stubs — `dummy.c`). The binary is **365 KB** — the entire game,
  smaller than one wallpaper.
- The shareware `doom1.wad`, pulled from Debian's `doom-wad-shareware`
  package, md5-verified against the canonical file
  (`f0cefca49926d00903cf57551d901abe`).

The deployment was a comedy of a minimal system: no `scp` on the TV (the
binary and WAD went over as `cat | ssh 'cat > file'`), no `nohup` (our
static busybox's `setsid` covered it), and the framebuffer *refuses
`read()`* — vendor fbs are mmap-only — so a 20-line `fbcat` helper
(cross-compiled the same way) became the screenshot tool.

The proof: E1M1's hangar, the pistol up, two imps down on the floor,
HEALTH 34%, doomguy bleeding in the status bar at 1920×1080. And the
next morning it got *playable*: the remote turned out to be Bluetooth,
not IR — the MStar IR receiver sits silent while the "Hisense" HID
device carries everything as standard Linux key events. The map took
one capture (UP=103, DOWN=108, LEFT=105, RIGHT=106) plus a surprise:
**OK is keycode 352, `KEY_OK`** — a dedicated Linux keycode, not Enter.
Arrows feed the doom arrows, OK feeds Enter, unknown buttons log
themselves to `doom.log` so the map teaches itself.

Then the last rite: a **Doom tile in the launcher's app row**. Pressing
it opens a near-blank page that tells the Pi's server, which spawns the
binary over the root SSH channel and lets it own the framebuffer; the
page goes black so the browser stops painting; pressing HOME kills Doom
and the watcher bounces back to alvidaa. The app row reads
Live TV · YouTube · Spotify · Browser · Recon · **Doom** — a 1993 game
sitting where the sponsored tiles used to be.

The tally: cert-gated MQTT, the browser bridge, the errno escape, the
boot hook, five locks, one key — and the last mile was 365 KB of 1993.

[📷 PHOTO 12: the actual TV in the living room, showing Doom]

---

## What owning it actually means

The honest map, because hype is cheap:

**What we have.** Boot-time root code execution, persistent, remotely
updatable over MQTT with zero physical contact. The file bridge as an
unauthenticated local API (uid 314, whole filesystem). Captured
credentials. A launcher we control end to end. A remote page loader
(`/api/open`). Remote reboots. Hook lineage with backups on the device.

**The hard wall.** Verified boot is locked and green — dm-verity squashfs
rootfs, `vbmeta device_state=locked`. The read-only system partitions
cannot be modified, ever, and attempting it is the brick. But nothing we
care about lives there: the UI, the ads, the apps, the JS services — all
on the writable partitions (`/APPS` even holds the stock home's own code:
`HI_UI_HOME=/APPS/channelA|channelB`). The cage is real; everything
valuable was stored outside it.

**The road ahead** — now written up as [LAUNCHER_V2.md](../launcher/LAUNCHER_V2.md),
phased so nothing bricks the party:

- **R0 — guardrails first (Done).** Frozen OTA/update endpoints with iptables
  in `/var/local/tvrc` (ota-tv.vidaahub.com blocked in-kernel and via DNS),
  outbound DNS/DoH locked to the AdGuard Pi, and hook idempotency preserved.
- **R1 — shell lands (Done).** Persistent Dropbear SSH on port 2222 across
  reboots, eMMC mapped (3.87 GB, 42 partitions), rootfs dumped and verified.
- **R2 — map the home plumbing (Done).** Traced Cobalt engine bootstrap,
  `HI_UI_HOME=/APPS/channelA`, and how `sdk.js` handles remote inputs.
- **R3 — telemetry kill at the kernel layer (Active).** iptables wiretap
  salvager active; caught `spectrum.s3.amazonaws.com` calling home over
  plaintext HTTP; deployed TV-scoped AdGuard filters and kernel rules.
- **R4 — alvidaa goes native (Achieved via overlay).** Rather than a fragile
  standalone engine rewrite, alvidaa achieved native residency directly on
  the TV via an append-only injection into `/APPS/channelA/hisenseUI/index.html`.
  Served by the Pi and rendered as a crisp 1080p HiDPI Canvas (`alvidaa-remote.js`),
  it runs directly inside Cobalt while the stock `sdk.js` runs underneath so
  remote keys and `HOME` route cleanly. Along the way we hit two big
  discoveries: Cobalt's Starboard parser discards scripts appended after
  `</html>` (must insert before `</body>`), and XHR from `file://` causes a
  reproducible CORS preflight deadlock in Cobalt — leading to a strict ban
  on XHR in favor of WebSocket-only transport.
- **R5 — stock home suppressed at the source (Achieved).** An injected
  `<style id="alvidaa-head-style">#app{display:none!important}html,body{background:#0a0d12!important}</style>`
  hides the stock `#app` and ad billboard at parse-time. The 1-second stock
  ad flash is dead; the TV powers up directly into a clean dark canvas and
  paints our overlay. Handled cleanly with `tools/deploy-overlay.sh` (1 TV write +
  `cobalt_home/*` cache wipe + synchronous reboot).
- **R6 — strip the ad components** out of the UI code on
  `/APPS/channelA` — the cleanest ad kill of all, not even
  network-dependent.

Still on the board, unscheduled: the alvidaa **GitHub publish decision**
(public would genuinely help other 2024+ VIDAA owners stuck on the
"app no longer compatible" wall — currently scattered across one giant
forum thread; private or local-only also fine), and naming the HDMI
inputs in config so the tiles carry names/glyphs.

[📷 PHOTO 12: the final home screen vs the stock one, side by side]

---

## Why write this down

Because none of this was one big break. It was twenty small ones, each
found by reading an error message — an errno that leaked a chroot base,
a SUBACK that silently denied wildcards, a timestamp-salted password, an
uptime that caught a fake reboot, a root-owned log file that proved its
own exploit. The only reason they compounded is that every
single one got written down the moment it happened. FINDINGS.md is the
real deliverable; this post is just its highlight reel.

And because "owning" hardware you paid for shouldn't be a scavenger hunt.
It took one weekend, two AI sessions running in parallel (one building
the launcher, one cracking the TV — logs pasted between them at 2am
energy), a Raspberry Pi, an unplugged TV, five dead PIN codes, and zero
screwdrivers. The TV wasn't flashed, jailbroken, or bricked. Verified
boot stays green. Delete the Home app entry, or factory-reset, and it's
stock again — every step reversible by design.

And when this story closes, the last photo is already chosen:
`ls /var/local/` with the hook deleted, a fresh boot counting from
uptime zero, the stock home on screen — verified boot still green, stock
in every way that matters. Every step of the weekend was designed
backwards from that shot.

It just said alvida to its ads.

[📷 PHOTO 13: the living room. TV on the alvidaa home screen. Nothing sponsored.]

---

## Timeline

| When | What |
| --- | --- |
| Oct 27, evening | Plan written; Fire TV Stick debloated (14 packages, 1 protected-refused, journaled + reversible); both toolkits scaffolded; "functional over fancy" locked as the design law. |
| Oct 29, morning | Pi resurrected post-SD-failure; TV fingerprinted (`transport_protocol=3290`); server + page + pair.py written; the 2024 cert gate diagnosed. |
| Oct 29, midday | APK AirDropped → `CN=VidaaAppAndroidV01` extracted → MQTT session established; the five-PIN war; wildcard-subscription and array-payload traps found. |
| Oct 29, ~15:45 | `hisense://debug` dead → self-install via `HiUtils` → **"woah. i installed and it shows up and works."** |
| Oct 29, ~16:15 | Repo spun out; named **alvidaa**; FINDINGS.md born; bug-list sprint; Pi deploy on 8770; v1.2 (logos) and v1.3 (WS fix, allowlist, wallpapers). |
| Oct 29, evening | "Check online for firmware gaps" → no public root for 2024+ → recon v1–v8 ladder built and climbed in ~90 minutes. |
| Oct 29, night | `rc.local` root primitive found; hook armed; fake reboot exposed by `/proc/uptime`; **wall plug pulled** → **ROOT CONFIRMED**. |
| Oct 29, late night | Hook v2 harvest (toolbox, shadow, applet inventory), hook v3 (busybox-over-`/dev/tcp`), dropbear cross-built with `zig cc`. Hook v4 fired → **Hisense's EULA firewall discovered** → hook v5 punches the holes. The five-lock gauntlet (firewall, key path, `/etc/shells`, the `chmod 777` perms walk, and the gate-as-shell costume) cleared version by version — **hook v10: `ssh -p 2222` lands at a root shell. Jailbreak complete.** First hour of ownership: eMMC mapped (3.87 GB, 42 partitions), `server/tv` wrapper, and the verity rootfs (p20) dumped to the Pi and unpacked — `cli-login-aes.pem` in hand. The actual project begins. |
| Oct 30 | Doom goes playable (BT remote on `event3`, OK=352) and gets a launcher tile; R0 guardrails applied via `tvrc` (DNS close verified, OTA host frozen); wiretap salvager installed — first catch: the TV calls an Amazon S3 bucket over plaintext HTTP (`spectrum.s3.amazonaws.com`). Tailscale joins the TV; repo published. |
| Nov 1–2 | Full partition backup & DoH kill-list: verified and mirrored all 42 eMMC partitions; decoded the `hiutils` HMAC-SHA1 security-code forge (`setDebugPort`); shipped tiered AdGuard + `tvfw` kernel blocklists; published the `09.60V` / `MTK9603` patched-firmware playbook. |
| Nov 3 | Native launcher overlay goes LIVE on TV: append-only injection into `/APPS/channelA/hisenseUI/index.html` with parse-time stock suppression (`#app` hidden, 1-second ad flash dead); diagnosed the Cobalt Starboard parser trap (scripts after `</html>` discarded) and the Cobalt XHR preflight deadlock (banning XHR for pure WebSocket); shipped 1080p HiDPI canvas overlay (`alvidaa-remote.js`) with deterministic `deploy-overlay.sh` deploy tool; TV DHCP lease moved to `192.168.0.11` (AdGuard rules and tools updated). |

## Photo shopping list

1. Stock VIDAA home (before)
2. Fire TV ADB dialog / retry ladder
3. SSDP fingerprint terminal
4. Pairing handshake working
5. The (fifth) pairing code on screen
6. First render in the TV browser
7. The Pi + `alvidaa.service` journal
8. Launcher v1.3 hero shot
9. Recon page / recon report
10. The unplugged plug
11. Root shell over telnet
12. Native overlay live on TV (1080p canvas, clock, green bridge status dot, HDMI & app tiles, zero ads)
13. Living room, final state

## Credits

Standing on the shoulders of
[Bananamafia's hisensehax](https://bananamafia.dev/post/hisensehax/),
[d3nd3/Hisense-mqtt-keyfiles](https://github.com/d3nd3/Hisense-mqtt-keyfiles),
[Krazy998/mqtt-hisensetv](https://github.com/Krazy998/mqtt-hisensetv),
[stevene1919/hisense_vidaa](https://github.com/stevene1919/hisense_vidaa/issues/6)
(the issue thread that cracked modern auth),
[Zfinix/vidaa-launcher](https://github.com/Zfinix/vidaa-launcher) and
vidaa-edge (mechanism references — independent
implementations), [giofrida/Hisense-Smart-TV-Enhancements](https://github.com/giofrida/Hisense-Smart-TV-Enhancements),
the humblemuzzu "dumbtv" / smart-tv-debloat school of "ads off, clutter
out, everything reversible," and `morluto/rea` for the RE toolkit.

*Everything here ran on a TV I own, through the TV's own APIs, fully
reversible — no system partitions were modified, verified boot stays
green, and the stock behavior is one deleted app entry away. The TV's
DNS is locked down in AdGuard Home, and it should be on yours too:
its browser exposes filesystem-level bridges to any page it opens, its
boot scripts run scripts from writable storage as root, and its
telemetry stack has names.*
