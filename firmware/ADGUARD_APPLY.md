# Applying adguard-blocklist.txt to AdGuard Home

How to turn the tiered list in this directory into live per-client DNS rules
on the Pi's AdGuard Home (`192.168.0.85`, native install at
`/opt/AdGuardHome`, v0.107.79). Operational mirror with the deployed
converter script: homelabbr repo `pi/services/adguard/` (README, procedures,
current client inventory). Wiki docs: homelabbr `wiki/wiki/services/adguard-home.md`.

## Client inventory

| AdGuard client | Identifier | Device |
| --- | --- | --- |
| Hisense VIDAA TV | `192.168.0.11` | WiFi MAC `bc:5c:17:bc:46:88` — **moved from `.12` ~2026-11-01**; `.12` is now a TP-Link device |
| Fire TV Stick | `192.168.0.82` | WiFi MAC `dc:a0:d0:60:b9:73` |

⚠️ Static DHCP reservations for both TV MACs are pending (router-side, owner
action). Until then, every rule below is keyed to a volatile IP — after any
DHCP churn, re-check the TV's source IP in the AdGuard query log and re-point
(`$client=` tags, client `ids`, and the tagged Perflyst lists).

## Step 1 — tier rules (custom filtering rules)

Paste `adguard-blocklist.txt` rules as **custom DNS rules** scoped to the TV
client. Every rule must carry the `$client` tag, and the single-`|` anchors
normalize to `||` (domain + subdomains):

```
||evt-na.vidaahub.com^$client=192.168.0.11
||ter-jrnl-na.vidaahub.com^$client=192.168.0.11
||exc-jrnl-na.vidaahub.com^$client=192.168.0.11
||policy-jrnl-na.vidaahub.com^$client=192.168.0.11
||dvcstatus-dataretrv.vidaahub.com^$client=192.168.0.11
||file-ul.vidaahub.com^$client=192.168.0.11
||rsc-ads.vidaahub.com^$client=192.168.0.11
||recommend-ui.vidaahub.com^$client=192.168.0.11
||home-ui.vidaahub.com^$client=192.168.0.11
||layout-ui.vidaahub.com^$client=192.168.0.11
||layout-ui-eu.vidaahub.com^$client=192.168.0.11
||topic-ui.vidaahub.com^$client=192.168.0.11
||abtest-tv.vidaahub.com^$client=192.168.0.11
||sport-vidaa.vidaahub.com^$client=192.168.0.11
||dns.google^$client=192.168.0.11
```

Tier 3 (`dns.google`) is load-bearing: the TV resolves `vidaahub.com` via
dns.google DoH by design, so plain-DNS rules only bind once the bootstrap is
blocked. The KEEP ALLOWED section of `adguard-blocklist.txt` (`ota-tv`,
`vidaa-base-auth{,-eu}`, `geo-bas*`/`time-bas-na`, `img`, store, voice) must
NOT be pasted as rules — `ota-tv` is frozen at the kernel layer (`tvfw`
rejects `131.189.69.51`), not at DNS.

Also live beyond the tier file: `||spectrum.s3.amazonaws.com^$client=…`
(S3 telemetry caller found via the query log) and
`||file-dl-test.vidaahub.com^$client=…`.

## Step 2 — Perflyst blocklists (tagged local copies)

AdGuard Home has **no per-blocklist client assignment in any version**, so
the three Perflyst lists are tagged rule-by-rule with `$client=` and installed
as local path filters under `/opt/AdGuardHome/userfilters/` (`safe_fs_patterns`
only accepts that path family): `SmartTV-AGH.txt` → TV, `AmazonFireTV.txt` →
Fire TV, `SessionReplay.txt` → both. Regenerate with `tag-perflyst.py`
(homelabbr `pi/services/adguard/`, deployed on the Pi next to the lists) after
upstream updates or IP changes, then re-add each list or restart AdGuardHome.

## API notes (v0.107.79)

- `/control/login` takes `{"name", "password"}` — **not** `username`.
- `/control/clients/add` takes a single object; `/control/clients/update`
  takes `{"name": ..., "data": {...full client...}}`.
- `filtering/set_rules` reloads asynchronously (~seconds) — an immediate
  `check_host` can read stale state.
- Verify per-client behavior with **GET**
  `/control/filtering/check_host?name=<domain>&client=<ip>` — it returns the
  exact matching rule for that client.

## Credentials

Dashboard credentials are not committed. Intended store: Infisical `/adguard`
(pending).
