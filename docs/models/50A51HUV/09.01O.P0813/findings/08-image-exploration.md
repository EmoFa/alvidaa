# alvidaa findings — image exploration — Loewe bones, the ODM platform

> Split from the original FINDINGS.md lab notebook. Canonical record; the blog and STORY.md draw from these.

## 12. Image exploration (Oct 2026)

Walked via `/sbin/debugfs` on the Pi (ext4) and unsquashfs (p20). Dumps in
`pi:~/firmware/`, extracts in `/tmp`.

- **The firmware is a multi-brand ODM platform with Loewe bones.**
  `/usr/local/configuration/options/dclkeys.cfg` is Loewe's DCL config format
  (`loewe/common/syscfgservice/...` paths in the comments, `chassisname HL1`,
  clone config `LoeweSl22x.dat`) — Hisense's VIDAA stack sits on top of the
  Loewe chassis framework. `kilby/` ships per-brand channel service lists
  (Cvte, CvteBoe, Cultraview, CtvAu/Eu, CulAu/Eu…) and `huangdao.db`
  (黄岛 — Hisense's Qingdao campus) — one firmware, many brands.
- **Identity**: `/usr/local/swver.txt` = `SWVER: 2.99.0.0; DEV; BUILD BY:
  gfkfcmo@3115006ccd7d` — a DEV-marked build; `/etc/biz_feature.json` flags
  `isSupportIPK:true` and `kilby-tvruntime-coldboot-update:true`.
- **VIDAA cloud endpoints (from `tvmain` strings)**: `geo-bas.vidaahub.com`,
  `vidaa-base-auth{,-eu}.vidaahub.com`, `layout-ui-eu.vidaahub.com` (the home
  layout is cloud-served!), `file-dl-test.vidaahub.com/promovod/` (promo/VOD
  pulls — the ad pipeline), `hisense-0ba453d1.prod.partner.netflix.net`,
  Gracenote (`cddbp.net`), plus Loewe-era German test URLs (spiegel,
  tagesschau, antenne.de) still in the binary. Live traffic adds Tencent
  (phoenix, 43.157.127.133:10443) and Alexa (avsservice → 35.71.160.28).
- **Telemetry API surface (tvmain strings)**: `*LogReport` calls for network
  status/connect-fail reasons, power-off, miracast, CEC, and
  `updateDataProtectionStatusToLogReport` — all funneling to
  `hi_logreport_service` on 127.0.0.1:1969, which every process reports to.
- **Firewall scripts found** (`/usr/local/scripts/firewall-{eulaon,eulaoff,-init-subrule}.sh`):
  EULA state changes run `iptables -F INPUT` then re-jump `FIREWALL_IN_EULAON`,
  guarded by a flock on `/tmp/firewall.lock` — confirming the re-apply loop in
  the boot hook is required, not just cautious.
- **CVTE factory logger** (`cvte-logger.sh`): with a `FAC_BOOT_SMART.cvt` file
  on a USB stick it **remounts `/` and `/usr/local` read-write** and copies
  logs out — factory remount primitives exist in shipping scripts.
- Still streaming at last check: p22/p24/p26/p36/p34/p17/p27/p41 (`/APPS` —
  the ad-surgery target).
