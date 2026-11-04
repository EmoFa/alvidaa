---
title: "Saying al(vidaa) to my Hisense TV"
description: "No ADB, no public root for 2024+ VIDAA. I built a launcher through the TV's own API, then walked the same door to root."
seoDescription: "How I rooted a 2024+ Hisense VIDAA TV: the MQTT bridge, a self-installing launcher, a browser-bridge sandbox escape, and an rc.local root hook."
image: /img/blog-sketches/unique/alvidaa-stamp-trim.png
imageAlt: "Transparent monochrome sketch of a TV with drooping antennas, ad tiles floating away, and a clock on screen"
date: 2026-10-29T00:00:00.000Z
updated: 2026-10-29T00:00:00.000Z
authored_by: ai-assisted
hidden: true
giscusTerm: "/blog/homelab/alvidaa/"
tags:
  - Self-Host
  - AI
---

{% update "2026-10-29" %}
Written live while the project happens — the SSH section at the bottom is literally still in flight as I type this.
{% endupdate %}

For the last few days I've watched from the sidelines while everyone and their grandma "hacked" and dumbed down their TVs. That mostly meant Android-based OSes: swap the launcher for a custom one, adb out some packages to trim the bloat. {% annotate "said the man with the un-hackable TV", "right" %}Rookie stuff{% endannotate %}, said me — with the sour-grapes energy of owning a Hisense TV running VIDAA OS. I hated it so much I bought a Fire Stick to replace it (and then did the same ADB-style "hacking" on the stick).

Note that VIDAA is Hisense's proprietary, locked-down Linux. No ADB. No dev mode. Nothing. And it had two gripes that bothered me to no end:

- **Incredible telemetry** — disabled through every setting possible, still phoning home.
- **Not defaulting to last source** — despite my best efforts, it would always land on the VIDAA ad-infested homepage instead of going straight to the Fire TV. Yes, I tried every setting out there.

Seeing all the RE writeups, decomp drama, and clones, I wondered: given enough free time, tokens (thanks, Global build of Z Code), and a willing[^1] chinese[^2] model like GLM 5.3 Flash — could I gain root access to the shell, thereby gaining a higher sense (hisense) of the TV, finally saying al(vidaa) (goodbye in Urdu — hence the repo name), and unlocking true hacking opportunities, not your run-of-the-mill ADB:

- true custom launcher
- firmware mods

And that I did. ~300M tokens and a couple hours of running recons on the MQTT bridge later, I finally got the message from our friendly chinese model. Here's the AI write-up of what transpired.

---

## The wall that stops everyone

The spec came first, and it never changed: **a clock, my HDMI inputs, my real apps — nothing else.** Functional over fancy. A launcher that can't be enshittified because it has no feed to enshittify.

The mechanism existed before the project did: VIDAA TVs expose a **RemoteNow** channel — MQTT over TLS on port 36669, the exact channel the official phone remote app uses. Publish an action, the TV obeys: launch app, switch source, send keys. So the plan was a web page + a small server that speaks RemoteNow. Every guide on the internet does this with static credentials from 2018.

On my 2024+ firmware, the TV answered all of that with a popup:

> *"Your TV mode is no longer compatible with the version of the app. Please try with the latest version."*

MQTT rc 5, Not authorized. Every guide, dead. The key turned out to be buried in issue #6 of a half-abandoned repo: 2024+ firmware checks the **client certificate's identity at the MQTT layer** and only accepts the cert belonging to the current official VIDAA Smart TV Android app (`CN=VidaaAppAndroidV01`). So we pulled the official APK (the mirrors hard-block bots, so the `.apkm` got AirDropped from my phone), dug the keystore out of `res/raw/`, and `openssl pkcs12 -legacy` later, the TV accepted our TLS handshake for the first time.

The cert alone wasn't enough — modern firmware also wants *dynamic* per-connect credentials: an MD5 digest of the TV's MAC, a username XORed with a hardcoded 64-bit constant, a password salted by the digit sum of the unix timestamp. Someone at Hisense had fun with this.

Then the pairing ritual: the TV shows a 4-digit code, you type it in. Except our keepalive — meant to hold the dialog open — re-triggered it every few seconds, and **every re-trigger rotates the PIN**. Five codes died on that hill before the lesson landed: trigger once, wait, submit. (There was also a trap where the TV talked and we were deaf — this firmware silently denies wildcard MQTT subscriptions, so a naive client publishes fine and hears nothing back, ever. Exact topics only.)

After that: paired, tokens captured (2-day access, 30-day refresh — pair once, stay paired), and the bridge was ours. App lists, source switching, key injection, TV state.

## A TV that installs its own launcher

The launcher itself is one HTML page drawn on a **single canvas** — the TV's browser can't composite normal HTML/CSS, so you draw everything and repaint cheaply. The page is stateless; all config and state get pushed by the server over a WebSocket. If the server dies, the clock keeps drawing and the page reconnects itself.

The last mile was the good part. The classic install door (`hisense://debug`, a hidden installer page) is closed on this firmware. But reading a modern VIDAA web-app project revealed something better: **the TV browser exposes its install bridge functions to any page it opens.** So the launcher page detects them and shows an `＋ INSTALL AS APP` tile — the TV opens its own app registry JSON, writes itself in, and one restart later "Home" boots like a native app. The TV installed its own replacement launcher from a plain HTTP visit.

> "woah. i installed and it shows up and works. how can we make this the default app and there is so much to do now… lets branch this whole thing out as a separate repo… and document findings so far like the cert thing and what not. so so much work hahaa lets"

So it became a repo — **alvidaa**. *Alvida*, goodbye. VIDAA. Alongside the code went the project's real deliverable: `docs/models/50A51HUV/09.01O.P0813/FINDINGS.md`, a lab notebook where every discovery gets written down the moment it happens. Every bug, every trap, every errno. That discipline is the only reason what happened next was possible.

The polish era compressed to one paragraph: a watcher that relaunches Home whenever the stock UI appears (~1 second of stock screen is the honest ceiling without root — VIDAA has no default-launcher setting), a config-driven allowlist that hides the apps I never asked for, real app logos proxied and cached from the TV's own CDN, generated wallpapers, and the whole thing deployed to the always-on Raspberry Pi as a systemd service. It became an appliance.

## The same door, walked further

Which brings us to the evening of the same day, and the message that turned a launcher project into a root project:

> "look online if firmware hacks exist for vidaa os and see if you can come up with a backdoor to gain root access to my tv"

The literature review was short: **no public root method exists for 2024+ VIDAA.** The deepest writeup in the community (Bananamafia's hisensehax) never got root. No CVEs. Everything published is pre-2021.

But we weren't starting from zero. We held something nobody had publicly pushed past its intended use: the `HiUtils` file bridge — read/write files, from JS, inside the TV's browser. So we built `recon.html`: a self-reporting probe page, one version per question, each run POSTing what it found back to the Pi. The ladder, in four beats:

1. **Who are you?** MediaTek MTK9602, 4K panel, firmware `V0000.09.01O.P0813` — and the browser is Chromium 111, not the Chrome 77 every writeup (including ours) swore by. The file bridge is sandboxed to `websdk/`. For now.
2. **Can we leave?** A *failed* absolute read leaks its errno; the errno leaks the sandbox base; and `../` walks straight out to the real root. Arbitrary read/write as the bridge's uid, filesystem-wide. SELinux turns out to be *permissive* — the boot script literally calls `setenforce 0`.
3. **What runs here?** The bridge's backend is "phoenix" — a Node.js server running its own source code off a partition we can write. Verified boot is active and green (the read-only system partitions are a permanent no-fly zone), but `/APPS`, `/data`, `/var/local`, and the OTA staging partition are all read-write, and the UART serial console is live behind a script-gated login.
4. **Is there a door?** In `rc.local` — run as **root** at every boot — this:

```sh
if [ -e /var/local/otaTest.sh ]; then
    chmod +x /var/local/otaTest.sh
    /var/local/otaTest.sh &
fi
```

`/var/local` is the rw partition the bridge can write. **Writing that one file is arbitrary code as root at next boot.** An OTA auto-test hook left armed in production firmware. No crypto, no symlinks, no config parsing.

One more trick made all of this couch-operated: the server gained a one-line `/api/open` endpoint that loads any URL on the TV through the existing MQTT session. New recon versions installed themselves remotely. Zero physical contact.

Then the comedy. We armed the hook and "rebooted" the TV. Nothing. The report came back and `/proc/uptime` said **26.6 hours** — the reboot had been a standby round-trip, and standby never re-runs `rc.local`.

{% annotate "some lessons still require physically unplugging the television", "left" %}Pull the wall plug for 30 seconds.{% endannotate %}

Thirty seconds of darkness later: uptime **250 seconds**, and the smoking gun — `/var/local/otaTest.log` **exists but is unreadable**, root-owned, because the hook chmod'd its dumps to world-readable and forgot its own log. Failure as evidence: the file could only exist if the script ran, and it could only be denied if the script ran *as root*.

**Root: confirmed.** The harvest came back through the bridge — process map, listening ports, the root-only gate scripts, and `/etc/shadow` with root's hash in it.

> "bruv. that is insane. … i am getting excited about owning this hardware finally."

## How it actually worked (for normal humans)

The through-line worth noticing: **at no point did anyone break anything.** The TV told us everything, politely, one honest error message at a time.

**The superpowers in the browser.** Your TV's browser gives pages secret powers — JavaScript functions wired straight into the TV, like a hotel room phone connected to the front desk. One of them can read and write files. It's supposed to only reach one small folder — your phone can call room service, not the other rooms.

**The jail that told us where its walls were.** Ask a computer for a file it can't open and it doesn't just say "no" — it leaves a note explaining why, and that note usually includes the full path it tried. We asked for a forbidden file, and the note came back: *"tried to open `/APPS//etc/passwd`."* The jail had just confessed its entire mechanism: it glues `/APPS/` onto the front of every path. So we asked for `../etc/passwd` — in path-speak, "go up one folder." Up, and out. We never picked the lock; we read the instructions printed on it.

**The back door with a welcome mat.** Those browser powers are just translators, forwarding requests to a helper program on a port that only exists *inside* the TV. Every request gets stamped with a rotating secret token, like a wax seal that changes each time. So we captured a stamped request, then replayed it without the stamp. The helper answered anyway — and its "who is allowed to talk to me" settings were wide open, meaning any webpage the TV's browser ever loads could use it. The bouncer checked wax seals at the front door; the back door had no lock and a welcome mat.

**The maintenance door, opened by the manufacturer.** A guest badge isn't root, so we read the boot scripts (thanks, previous step) — the building's morning routine, left on the front desk. In one of them: *if this specific file exists, run it as root.* In a folder we could write to. A leftover update-test hook, armed in shipping firmware. Write the file, reboot, and the TV voluntarily runs our script as admin — every boot, forever. We didn't defeat the security; we used the maintenance entrance, and the only design flaw was assuming no webpage could ever reach that folder.

(The firewall twist — the guard who caught us and turned out to be on our payroll — completes this story two sections down. It's the best one.)

## What owning looks like

The honest map, because hype is cheap:

- **What we hold:** boot-time root code execution (persistent, remotely updatable over MQTT, hook lineage backed up on the TV), the file bridge as a local API, captured credentials, remote page loading, remote reboots.
- **The wall that stands:** verified boot, locked and green. The read-only system partitions cannot be modified — and don't need to be. The UI, the ads, the apps: all on the writable partitions. The cage is real; everything valuable was stored outside it.
- **The road:** dump the firmware over the shell into Ghidra. Kill ads in-kernel with the `iptables` binary that ships on the box. Then the real prize — the launcher server moves *onto the TV* (there's a Node runtime right there), the Pi retires, and the last ~1 second of stock UI dies with it.

And the current frontier, live as I write: the TV has no SSH server at all and its busybox lacks `telnetd`, so we cross-compiled a static **dropbear 2025.88** for its armv7 with `zig cc` and shipped it to the hook. The boot log read `TELNETD-OK` / `DROPBEAR-OK`, host key generated — and yet SSH just *timed out*. That word choice was the clue: "refused" means nobody home; "timeout" means someone is catching your packets and dropping them on the floor, silently. The hook had already dumped the firewall rules at boot, and there it was — my favorite find of the night: **Hisense ships its own anti-tamper firewall.** INPUT jumps to a `FIREWALL_IN_EULAON` chain — allow MQTT, ICMP, loopback; **DROP everything else**, with an explicit blacklist of debug ports: 22, 23, 4444, 9222 (Chrome devtools!), 12321. They anticipated exactly this class of attack and locked the debug ports down at the kernel layer. It just defended the wrong direction: the firewall watches the perimeter, and our attack never knocked — it walked in through the web browser, got admin, and then, as the firewall's own administrator, read the blacklist with the firewall's own `iptables` and added our ports to the allow list. The building's security guard caught us, and then it turned out we'd hired him. Hook v5 (installed remotely, lineage preserved) re-applies those rules in a loop for the first minutes of boot, so later boot stages can't quietly reload the firewall around us.

{% update "2026-10-29" %}
Status at draft-time: the firewall hole works — dropbear answers with a real `Permission denied (publickey)`, which is daemon-speak for "alive, come back with the right key." One mundane bug left: dropbear's `-D` replaces the `.ssh` directory itself, so the key belongs at `/var/local/roothome/authorized_keys`, not in a subdirectory. Being fixed live over the telnet shell. The plug has not had to come out since the root pull.
{% endupdate %}

## The telemetry shelf

The part I asked about early — *"check what sort of telemetry games they are up to"* — now has names, straight off the TV's own process table: `hi_logreport_service`, `mdharvester`, `write_stat`, `bizm`, plus a `GetAdsID` bridge on the TV's public API. Public research has already flagged VIDAA's viewing-tracking server as having no authentication.

Two findings make the network layer non-optional:

- The file bridge answers **unauthenticated, with `Access-Control-Allow-Origin: *`**, on the TV's localhost — any page the TV browser ever opens has filesystem access as the bridge user.
- The same browser exposes the silent app-install trick to any page. (That's how our launcher installed itself. It works both ways.)

So: the TV's DNS is pinned to AdGuard Home with per-client blocklists (Smart TV list, session-replay list), and the plan is to mirror that in-kernel with `iptables` from the boot hook, then log what actually phones home for a few days and block everything that isn't firmware updates.

---

Why write all this down? Because none of it was one big break — it was twenty small ones, each found by reading an error message, and they only compounded because every one got documented the same hour it happened. The full gory detail lives in the repo's [FINDINGS.md](https://github.com/carteakey) (GitHub publish pending my courage). The TV wasn't flashed or bricked; verified boot stays green; delete one app entry and it's stock again. Everything reversible, by design.

It just said alvida to its ads.

[^1]: The polite models take one look at "root my TV" and reach for the disclaimer template. It's my TV. On my LAN. Against nobody.
[^2]: The willing one. GLM 5.3 Flash didn't blink — just asked for the TV's IP.

{% callout "todo", "Photos to drop in before this leaves draft" %}
1. Stock VIDAA home — *the billboard* (hero image, the before shot)
2. The pairing code on screen — *the fifth one. the good one.*
3. alvidaa home screen running — *clock, inputs, apps, nothing else*
4. Recon report JSON or the INSTALL ROOT HOOK button
5. The unplugged wall plug — *highest-leverage thirty seconds of the project*
6. Root shell over SSH — *no more plug pulls*
{% endcallout %}
