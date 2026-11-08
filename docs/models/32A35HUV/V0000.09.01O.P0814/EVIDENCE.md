# Evidence — 32A35HUV / V0000.09.01O.P0814

All claims below were observed on the reporting unit. Panel captures and
command transcripts exist for every row; identifiers are redacted per repo
policy (MACs, serial, DeviceId, LAN IPs → placeholders).

| Claim | Evidence | Status |
| --- | --- | --- |
| `transport_protocol=3290` | device descriptor `modelDescription` via SSDP `M-SEARCH ssdp:all` | verified |
| SoC MTK9602, firmware V0000.09.01O.P0814, VIDAA U09.01, Chromium 111 | browser census page: `Hisense_GetChipSetName()`, `Hisense_GetFirmWareVersion()`, UA string | verified |
| CAN region | census `Hisense_GetCountryCode()` = CAN | verified |
| Pairing works, coloned MAC required | bare Wi-Fi MAC: all four credential profiles rejected (rc=135); coloned format + modern profile: PIN flow, token issuance | verified |
| Launcher installs and runs | `HiUtils_createRequest` fileRead/fileWrite of `websdk/Appinfo.json`; tile present in the home grid after reboot | verified |
| File-bridge traversal open | census page: `../etc/passwd`, `../proc/mounts`, `../proc/partitions`, `../etc/inittab` read from a page in the home engine | verified |
| File-bridge write open | `/var/local/otaTest.sh` written over the bridge, readback byte-verified | verified |
| Root achieved (boot hook) | proof hook dump: `UID=0 EUID=0` at uptime ~6 s after cold boot, read back over the bridge | verified |
| Key-only root SSH | dropbear 2025.88 on 2222 (`-D roothome -s`), session as uid=0 | verified |
| `537.js` = menu UI + surface handoff | removing the chunk: menu gone AND app launches never display (bisected, screen captures) | verified |
| Opaque CSS canary breaks promotion globally | body-wide opaque/hiding CSS: all launches report ok, panel stays black (bisected, reverted) | verified |
| Empty `Appinfo.json` = permanent black screen | empty `AppInfo` array across reboots → solid frame; restored entry → renders (bisected) | verified |
| `/opt/iot/mosquitto` = RemoteNow broker (36669) | killing it drops the bridge session; restart with `LD_LIBRARY_PATH=/opt/iot/mosquitto/lib` restores | verified |
| ui_service state quirks (P0814) | `state` topic SUBACK refused; `gettvstate` silent; broadcast topic delivers | verified |
| Bounces pre-UI-ready never promote | early `launchapp` reports ok, no surface (observed during boot-bounce experiments) | verified |
| OTA freeze (R0) | OTA host REJECTed at the kernel OUTPUT chain; auto-update OFF in settings | verified |
| Full eMMC backup | 42 partitions, chunked over `/dev/tcp`, size-verified, SHA256SUMS manifest | verified |
| `euladpp_untar` | never probed | untested |
| `identity_gate` | never probed | untested |
| `devtools_forge` | never probed | untested |

Redaction note: MAC addresses, serial number, DeviceId, and LAN IPs are
replaced with placeholders throughout; raw transcripts stay off-repo.
