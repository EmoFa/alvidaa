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
