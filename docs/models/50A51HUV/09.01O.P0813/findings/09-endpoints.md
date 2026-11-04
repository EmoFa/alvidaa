# alvidaa findings — UI internals and the endpoint map

> Split from the original FINDINGS.md lab notebook. Canonical record; the blog and STORY.md draw from these.

## 13. UI internals & the endpoint map (Oct 30)

All 12 partition images captured (byte-verified). p41 `/APPS` walked:

- **R2's canary is live on channelA**: `index.html` (650 B) = the stock
  webpack loader + a red `alvidaa` badge div, with the original preserved as
  `index.html.alvidaa-bak` — the canary-edit path validated on the real UI.
- **The stock home is a thin shell**: `app.js` is 3.8 KB; `sdk.js` (883 KB)
  carries the platform logic. `process.env.json`: `BRAND: HIS, AREA: NA,
  PLAT: 9602, REPORT: false`. `hisenseUI` version `9.00.01.25.080417`.
- **The complete vidaahub.com service map** (~30 subdomains) lives in
  `sdk.js`: home-ui, recommend-ui, layout-ui{,-eu}, search-ui, topic-ui,
  detail-ui, member-ui, odinstore-vidaa, sport-vidaa, tvmodules-vidaa,
  pay-vidaa, msg, web, voice/vidaa-voice/iot-voice, ota-tv, file-ul,
  file-dl-test (promovod), device-ecom, oauth-auth, geo-bas,
  vidaa-base-auth{,-eu}. Plus `voiceservice-eu.hismarttv.com`.
- **`static/config/brand/` = ~50 three-letter brand configs** (his, lwe,
  jvc, phi, pan, tel, …) — theming only; the cloud map is brand-independent.
  `static/presetData/basicNationalInfo` = an image blob with national flags
  + info JSON (the "network-fed" national content).
- **Kill-list tiers drafted** in `firmware/ENDPOINTS.md` (gitignored):
  ALLOW = ota-tv/auth/geo-bas/icon-CDN; BLOCK = recommend/home/layout/
  topic/sport/promovod; LOG-first = store/pay/msg/voice/uploads.
- **Telemetry upload domain is runtime-resolved**:
  `hi_logreport_service` uses `getDomain`/`getDomainForUpload` against
  `vidaahub.com`; its API surface: `uploadFunctionSwitch`,
  `uploadGeneralFieldLog`, `uploadStoredSelfDefinedLogFile`,
  `uploadTvBacktrace`, `uploadOemOtaFailedFile`. Confirm the exact host
  from the `TVOUT` wiretap before blocking.
- `/data` (p27) = per-app silos (YTTV, amazon, netflix, vudu, airplay, QDA,
  webui) — third-party app state; keep images private.

## DoH evasion — the layer that beats DNS blocking

`/APPS/domain/domain_list.json` ships `dohServers: ["dns.google/dns-query"]` + `dohDomains: ["vidaahub.com"]` — vidaahub lookups bypass the LAN resolver via DoH by design. REJECT 8.8.8.8/8.8.4.4 :443 from the TV, then the fallback resolver (AdGuard) and its domain rules bite. Tiered lists: firmware/adguard-blocklist.txt + firmware/tvfw. The map self-declares the telemetry/ad hosts (evt-na, *-jrnl-na, rsc-ads, dvcstatus-dataretrv, file-ul) and is uid-314-writable via the bridge (mode 6).

## First wiretap window (Oct 30 – Nov 2, settings OFF)

1153 kernel-log lines harvested over ~26 h. Results:

- **447 DoH bootstrap attempts to 8.8.8.8:443** — the evasion fires
  constantly even with telemetry off. Countermeasure deployed live:
  REJECT 8.8.8.8/8.8.4.4 :443 (tcp+udp) at OUTPUT → lookups fell back to
  the LAN resolver (AdGuard) immediately (verified: `nslookup` answers
  from 192.168.0.85 post-deploy).
- **Telemetry confirmed despite settings OFF** — wiretap SYN hits match
  the domain map by IP: `ter-jrnl-na` (data-tenant-fluentd, 20.170.76.123,
  14 connections — a Fluentd log collector), `dvcstatus-dataretrv`
  (20.52.196.175), `file-ul`/account (131.189.128.123, plus 131.189.69.51
  same prod-eu-c range). The "off" settings do not stop the journal
  collector.
- Monetization range: 20.113.x (rsc-ads → monetization-tenant-ads) —
  now REJECTed at OUTPUT.
- Content CDNs (98.67.x, 48.201.x, 72.144.x, 13.227.x = CloudFront,
  172.217.x = Google, 89.187.x = cdn77) — UI/content traffic, left
  unblocked; they are not the ads feed.
- Tier-1 IP blocks deployed live over the tailnet (ter-jrnl + rsc-ads
  first) — the iptables layer and AdGuard layer now overlap.
- The hourly collector (`wiretap.log`) continues; the window stays open
  for the full baseline before the deliberate ON-capture.
