# Telemetry — 55S7NEVS

> From the contributed bundle by [possibly_matt](https://www.reddit.com/user/possibly_matt/)
> (2026-11-05), adapted for this repo 2026-11-06 with the author's permission
> for the documentation. "FACTS" and `guard/` pointers below refer to the
> author's private working notes and payload directory, which are not part
> of this repo. See the [guide README](../README.md) for scope.

What the firmware reports, when it phones home, who receives it, and what is
actually switched on **on this unit**. Derived from the 2026-11-03 eMMC
backup (`<EMMC_BACKUP>/`) plus the live
runtime snapshot (`meta/runtime.txt`). Vendor behaviour only; our own root
kit is excluded.

Read with `20-userspace-runtime.md` (services), `30-update-oad.md` (OTA
events), and `50-security-review.md` (the phoenix bridge / local read
primitive that makes some of this data reachable from a rendered page).

No personal content (messages, media titles, viewing history, real
MAC/serial) is quoted here; only counts, schemas, endpoints and vendor
text are used as evidence.

## Provenance

| On-device path | Backup snapshot |
|---|---|
| `/mnt/tvroot/...` | `fs/mnt_tvroot.tar.zst` |
| `/APPS/...` | `fs/APPS.tar.zst` |
| `/var/local/...` | `fs/var_local.tar.zst` |
| `/etc/...` | `fs/etc.tar.zst` |
| `/serialdata/...` | `fs/serialdata.tar.zst` |
| `/OAD/...` | `fs/OAD.tar.zst` |

Key artefacts quoted below:

| Artefact | sha256 |
|---|---|
| `/mnt/tvroot/usrlocal/bin/hi_logreport_service` | `83f95138…e44d0` |
| `/mnt/tvroot/usrlocal/bin/HamService` | `60234ee5…2196c` |
| `/mnt/tvroot/usrlocal/bin/ota_upgrade` | `4eae2eef…c5cce` |
| `/APPS/logservice/xml/report_policy_xml_file.xml` | `6e408d40…f19d4` |
| `/var/local/kilby/kireg-kilby0.dat` | `95fa9245…97f4f` |
| `/APPS/euladpp/current/eula_dpp_status.ini` | `8b09e587…46fa4` |

---

## 0. Bottom line

1. **There are two separate telemetry stacks.** A Hisense/VIDAA run-log
   service (`hi_logreport_service`, user `UhisLog`) and an Alphonso →
   Tremor → Nexxen **ACR / Enhanced Viewing** stack inside `HamService`.
2. The run-log service is **live and always-on**: it starts on every boot,
   is kept alive by APM, fetches a cloud policy, and is built to upload
   gzip+AES log bundles to `*.vidaahub.com`.
3. It collects **more than logs**: process tables, per-process `/proc`
   details, `/var/local` listings, WiFi driver info, dmesg/messages, app
   logs, **coredumps and backtraces**, and OTA deploy errors.
4. The upload policy is **cloud-controlled**. It contains 266 event codes,
   upload URLs, encryption/compression flags, timer/size thresholds, and a
   "self-defined log" job shape (`url`, `logger`, `playStat`, `maxCount`,
   `size`). That is a remote collection mechanism, not just crash reporting.
5. **ACR is the real privacy bomb** — continuous audio fingerprinting of
   anything on screen, hashed "Digital-print" + WAN IP + SmartTV identifier
   to `acr.unruly.co`, with vendor text saying the data may be **sold** and
   used for **ads on other devices sharing the same IP**.
6. **But ACR is off on this unit.** `/var/local/kilby/kireg-kilby0.dat` has
   `acr/switch = 0`; `eula_dpp_status.ini` has `pn4_enhance = 0`; Cobalt
   storage records a first opt-out on 2025-09-07 and three reminders.
7. Consent state on this unit: `eula=1`, `dpp_general=1`,
   `pn4_enhance=0`, `pn5_improvement=-1`, `pn8_advertisement=-1`,
   `pn9_datasharing=0`.
8. The log service was alive recently: policy XML dated **2026-10-31
   21:12**, `policySeq` rewritten **2026-11-02 22:29**. OTA event reporting
   last succeeded **2026-08-14**; the last version check returned
   `205001 no match upgrade rule` (GBR `upgradeFlag=0`).
9. **Local/LAN collection is broader than the cloud path.** DAB exposes
   `/device-telemetry/*`, `/app-telemetry/*`, `/output/image` (screenshot),
   `/input/key-press`, `/applications/launch`, and `/voice/send-audio`.
   MQTT `1883` is configured `allow_anonymous true` behind a vendor auth
   plugin. Support bundles (`getlog`) grab device ID, kids settings, and a
   timer DB whose schema contains PIN columns.
10. **No evidence** that the TV automatically uploads screenshots or local
    media metadata to the cloud. `capture`/`screenshot`, `mdharvester`,
    `write_stat`, and `getaudiolog` are local tools. The cloud path is the
    run-log service, OTA events, ACR (off), voice, and ads.

---

## 1. The telemetry map

| Channel | Process / binary | User | Transport | Endpoint | Gate | State on this unit |
|---|---|---|---|---|---|---|
| Run-log / diagnostics | `hi_logreport_service` | `UhisLog` | HTTPS POST, gzip+AES | `ter-jrnl.vidaahub.com`, `exc-jrnl.vidaahub.com` | EULA + DPP general, factory/hotel checks | running, policy cached |
| Device status / function switch | `hi_logreport_service` | `UhisLog` | HTTPS | `/1.0/bas/report/deviceStatus` | same | on power-on / log-switch change |
| OTA version check | `ota_upgrade` | `UhisOta` | HTTPS | `/upgrade/check_version` | network, country rule | runs on boot; GBR rule off |
| OTA event report | `ota_upgrade` | `UhisOta` | HTTPS | `/upgrade/report_upgrade_event` | network | last success 2026-08-14 |
| ACR / Enhanced Viewing | `HamService` + `libnexn`/`libwhspr` | `UhisHam` | HTTPS + MQTT | `acr.unruly.co/v2/device`, `/v2/inmarket` | ACR switch + EULA/DPP + country kill switch | **OFF** (`acr.switch=0`) |
| Voice (Alexa AVS) | `voiceservice`, `avsservice`, `ignition` | `UhisAvs` | HTTPS / CloudWatch | Amazon AVS + `api.hismarttv.com/voiceservice/*` | Alexa account/linking | running |
| Ads / monetization | `adService.js`, SystemUI | `UhisBrow` / SystemUI | HTTPS | `rpt-mntz.vidaahub.com`, ad strategy CGI | ad switch | `pn8_advertisement=-1` |
| Local DAB telemetry | MQTT/DAB | 372 | MQTT 1883 + localhost | `/device-telemetry/*`, `/app-telemetry/*` | DAB pairing/auth plugin | listener up, debug off |
| Support bundle | `getlog`, `getlog-pii`, `getaudiolog` | UART menu/root | local USB/OAD | none (local) | physical/key combo | available |
| Local media metadata | `mdharvester` | Kilby | local TCP + SQLite | `/var/run/granary.db3` | local | running |
| Local block tracing | `write_stat` | debug | local CSV | none | manual | tool present |

---

## 2. The run-log service (`hi_logreport_service`)

### 2.1 Startup and supervision

- `autorun_root.sh` starts it on every boot:

  ```sh
  /usr/local/scripts/start-logreport.sh &
  ```

  `start-logreport.sh` sets `LD_LIBRARY_PATH` and `exec`s
  `/usr/local/bin/hi_logreport_service`.

- `delayrun.sh` also starts it later via `start-hislogreport.sh` (both
  paths exist in the shipment).

- APM treats it as a kept-alive background app
  (`/mnt/tvroot/usrlocal/etc/apm/application-config.ini`):

  ```ini
  [hi_logreport_service]
  path = /usr/local/bin/hi_logreport_service
  app_type = bgAppType
  auto_start_in_factory_mode = 0
  registerToApm = false
  isKeepAlive = true
  restore_time_when_crash = 5
  ```

- Live snapshot: PID 2764, user `UhisLog`.

### 2.2 Policy fetch (cloud-controlled)

The service does anonymous device authentication, then asks the cloud for
a log policy:

- `HI_GLOBAL_INIT`, `HI_AUTH_AUTHENTICATE` (`libhi_cloud_openapi.so`).
- Policy endpoints in the SDK:
  - `/log/get_strategy?`
  - `/log/get_dotexception_strategy?`
  - `/log/get_log_policy_with_sign` (log-service binary)
- Upload hosts are **not hardcoded**. The SDK resolves an app-service list
  (`/pds/getAppServiceList?`) and reads `addressType="dasurl"` and
  `"strategy_all"`, then uses the policy's `serAddress` / `excAddress`.

Cached policy lives at:

```text
/APPS/logservice/xml/report_policy_xml_file.xml
/APPS/logservice/xml/report_obtained_policy_xml_file.xml
/APPS/logservice/xml/report_selfdefined_xml_file.xml   # not created here
/APPS/logservice/policySeq
```

Current policy values (from the 2026-10-31 XML):

| Field | Value | Meaning |
|---|---|---|
| `resultCode` | `0` | accepted |
| `serStatus` | `1` | service log upload on |
| `excStatus` | `1` | exception log upload on |
| `encrypt` | `1` | encrypt before upload |
| `compress` | `1` | gzip before upload |
| `serAddress` | `https://ter-jrnl.vidaahub.com/json/bin/na/ter/terminal` | normal log sink |
| `excAddress` | `https://exc-jrnl.vidaahub.com/json/bin/na/exception/terminal` | exception log sink |
| `dotAddress` / `heaAddress` | empty | other channels off |
| `netType` | `1` | network policy |
| `policySeq` | `1785720876` | policy sequence (2026-08-03 01:34:36Z if read as Unix time) |
| `serduration` / `serfileSize` | `30` / `20` | service-log timer / size thresholds |
| `excduration` / `excfileSize` | `30` / `20` | exception-log timer / size thresholds |
| `dotExcTagList` | **266 event codes**, all `eventStatus=1` | every listed event is eligible |
| `paramsTagList` | empty `logger` / `playStat` | no extra tags today |

The service logs `need Update Policy after 24 hours`, so the policy is
refreshed daily (and on boot / network return).

**Evidence it was alive recently:** policy XML mtime `2026-10-31 21:12`;
`policySeq` mtime `2026-11-02 22:29`; `policySeq` content matches the XML.
That proves policy processing. It does **not** prove a specific log batch
was uploaded — the per-run queues are in `/tmp` (tmpfs) and were not in the
backup.

### 2.3 What it collects

The event agent (`libhi_logreport_agent.so`) feeds it from `tvmain`,
`systemserver`, `sysmain`, `masman`, `dlna_service`, `chassis`, `biz`,
`avmain`, `apmbond`, `HamService`, `iot_service`, `SystemUI`,
`voiceservice`, and `airplay_bridge`.

#### Identity / device profile

Strings and observers in `hi_logreport_service` show it reads:

- `deviceId`, `devSerial`, `HW_GetHWMac` / `MacAddr` / `&MAC=%s`
- model, brand, chip platform, TV OS version, firmware version,
  `capabilityCode`, `FeatureCode`
- country, language, locale, panel resolution, `esnkey`
- `customerid`, `roleid`, `roletype`
- eMMC life (SLC/MLC), hotfix version
- boot session / boot-up time, wakeup reason, TV mode, TV start reason
- hotel mode, factory state, OpApp support, channel mode
- Dolby Vision / Dolby Atmos support, power use case
- `dvcstatus` / `dataretrv` tags for the device-status upload

#### Lifecycle / usage events

- app start, app video start, power on/off, source switch, WiFi connection
- CPU / memory / flash alerts
- coredumps and backtraces
- OTA failures (`/OAD/deploy_error.log`)
- UI, media playback, network, CI+ CAM, DRM, YouTube/browser errors
- "function switch" (feature/consent) changes

#### Diagnostic bundles on alerts

`/mnt/tvroot/usrlocal/scripts/logreport_gatherlog.sh` builds tarballs for
`appStart`, `appVideoStart`, `pucman`, `sourceSwitch`, `cpuAlert`,
`memoryAlert`, `flashAlert`, and `wifiConnection`. The CPU/memory paths
run these commands (output redirected into the bundle; redirects omitted):

```sh
top -b -n1
cat /proc/meminfo
cat /proc/stat
ps -o "user,comm,pid,ppid,vsz,stat,rss,args"
for l in `ls /proc | grep "^[0-9]"`; do
    cat /proc/${l}/stat
    cat /proc/${l}/cmdline
    cat /proc/${l}/statm
    cat /proc/${l}/status
done
```

The flash path runs `df`, `ls -l /var/local`, `du -sd1 /var/local`. The
WiFi path copies `wifidriveinfo.txt`, `/var/demsg`, `/var/log/messages`,
and `/var/log/log.txt` (+ `.1`). The app-start path copies
`/var/log/log.txt` and `.1`.

That is a **process table and filesystem inventory**, not just an error
message.

#### Coredumps and backtraces

`TvCoredumpThread` / `TvBacktraceThread` in the log service:

- watch `/var/crash/`
- upload `coredump` and `backtrace` files (`uploadTvCoredump`,
  `uploadTvBacktrace`)
- emit event `010001` with
  `{"errmsg":"TV_CORE_DUMP_APPEAR_ERROR","extramsg":"-1"}`
- track `/OAD/coredumpfiletransfertimes`
- suppress duplicate coredump uploads

Coredumps are process memory. They can contain tokens, URLs, app state, and
whatever the crashed process had in RAM.

#### Self-defined log job (remote collection)

The policy parser has a `SelfDefinedLogThread` and a
`report_selfdefined_xml_file.xml`. Its fields (from parser strings) are:

```text
url, logger, playStat, maxCount, size
```

The thread can `tarDebugFilg` / `unTarDebugFilg`, use `superWatchTarTool`,
and `uploadStoredSelfDefinedLogFile` / `uploadSameSelfDefinedLog`. In plain
terms: **the cloud can define a diagnostic job with a destination URL and
selection/size limits.** No such job is present on this unit (the
`report_selfdefined_xml_file.xml` was not created), but the capability is
shipped.

#### Device status / function switch upload

Separate from log batches, the service posts to:

```text
/1.0/bas/report/deviceStatus
  ?appOwnership=...&brand=...&commonInfo=...&deviceType=...
  &language=...&locale=...&model=...&tvMode=...&tvOsversion=...&uVersion=...
```

with `dvcstatus` / `dataretrv` tags. It is triggered on TV power-on and on
log-switch changes (`UploadFunctionSwitchFlag when tv power on`,
`UploadUncheckLogSwitchFlag when log switch change`).

### 2.4 How it uploads

- HTTPS POST, JSON headers:
  `{"Accept":"application/json","Accept-Charset":"UTF-8","Content-Type":"application/json"}`.
- gzip + AES + hex/base64:
  - `HI_SDK_GZCOMPRESS` / `deflate`
  - `HI_SDK_AES_ENCRYPTION` / `AES_cbc_encrypt` / `AES_set_encrypt_key`
  - `HI_SDK_ENCRYPT_TO_HEXSTRING` / `HI_SDK_ENCRYPT_TO_STRING`
- Upload query (from `libhi_cloud_openapi.so`):

  ```text
  policySeq=%s&deviceId=%s&appKey=%s&countryCode=%s&brandCode=%s
  &version=1&capabilityCode=%s&TVOSversion=%s&featureCode=%s
  ...&deviceType=%u...&languageId=%u&accessToken=%s...&refAppKey=%s
  ```

  body: `logmsg`.

- Offline queue (tmpfs):

  ```text
  /tmp/logservice/logfile/servicelogfile
  /tmp/logservice/logfile/exceptionlogfile
  /tmp/logservice/logfile/functionswitchlogfile
  /tmp/logservice/logfile/recordbacktrace
  ```

  Strings: "Default Offline Log into MsgQueue", "network reason, do not
  remove file" — logs are kept until network returns.

- Triggers: timer reached, size reached, active-file count reached, boot,
  log-switch change, coredump, OTA failure.
- `serduration=30` is read next to the log line `minutes is %d`, so the
  timer is 30 **minutes**. `serfileSize=20` is a file-size threshold; the
  policy does not label the unit.
- Consent gates: `get eula or pp switch close,so Any Logs donot need to
  report`; also factory-mode and hotel-mode checks.

**MAC inconsistency:** `ota_upgrade` has `desensitize_mac` / `mask_str`
symbols and the OTA docs say MACs are anonymised before send. The log
service binary has **no** `desensitize_mac` / `mask_str`; it reads
`HW_GetHWMac` and formats `&MAC=%s` / `mac: %s`. The OTA path masks; the
run-log path does not.

### 2.5 Event codes

The agent has a small fixed set of log types (mapping read from the string
order in `libhi_logreport_agent.so`):

| Code | Event |
|---|---|
| `001001` | app start |
| `002001` | app video start |
| `003001` | power on |
| `003002` | power off |
| `004001` | source switch |
| `005001` | WiFi connection |
| `006001` | CPU error |
| `007001` | memory error |
| `008001` | flash error |
| `010001` | coredump |
| `013001` | phoenix exception |
| `015001` | launcher service error |
| `200316` | ACR capable (vendor `Tremor`) |
| `200317` | ACR active (vendor `Tremor`) |
| `200318` | ACR AIAQ/AIPQ status (vendor `Tremor`) |
| `200319` | ACR consent event (step id) |
| `200340` | GTBillingDisplay (pay) |

The policy's 266 codes include these plus the UI/media/network/CI+/DRM/OTA
families (`2001xx`, `2010xx`, `2160xx`, `2400xx`, `2500xx`, `2600xx`,
`2700xx`, `2750xx`, etc.). The full list is in
`/APPS/logservice/xml/report_policy_xml_file.xml`; all entries are enabled.

---

## 3. ACR / Enhanced Viewing — the real privacy story

### 3.1 Who is behind it

- The privacy text is **Alphonso Inc.** (`alphonso.tv/privacy`,
  `alphonso.tv/terms`).
- The UI and EULA name **Tremor** / **Tremor Video** as the advertising
  partner.
- The shipped SDK is **Nexxen / Unruly**:
  - `https://acr.unruly.co/v2/device` (registration)
  - `https://acr.unruly.co/v2/inmarket` (region availability)
  - source paths `/builds/acr/libnexn/...`, `/builds/acr/libwhspr/...`
  - `acr.unruly.co` default config
- `start-hamservice.sh` sets the audio input:

  ```sh
  export NEXN_INPUT_SAMPLE_RATE=48000
  export NEXN_INPUT_CHANNELS=2
  export NEXN_CA_BUNDLE=/APPS/pkgs/tv.vidaa.phony.keystore/current/common/cacerts.pem
  exec /usr/local/bin/HamService
  ```

- `HamService` (user `UhisHam`, PID 4111) hosts both DLNA and the ACR
  controller.

### 3.2 What it does

From the SDK option table and source paths:

- Takes **48 kHz stereo** audio from the current TV source.
- Resamples to the fingerprint rate (defaults `fp-sample-rate = 8000`,
  `fp-channels = 1`).
- Runs FFT / minhash fingerprinting (`libwhspr`, `fftwf`), producing
  `WP1` messages.
- Sends fingerprints on an MQTT channel every **1 second** by default
  (`fp-send-interval = 1`); registers the device over HTTPS first.
- Tracks the audio source (`app_name`, `source`, `tuner_channel`,
  `hdmi_device`) so matches can be attributed to tuner/HDMI/app.
- Gets back match/recommendation data; can adapt picture/sound and feed
  recommendations (`kilby.sl2.i32.acr.*`).
- Has a country kill switch (`setCurCountryKillSwitch`,
  `kilby.sl2.i32.acr.kill.switch`) and an `anonymize` flag.

The SDK also has a **Datadog metrics path** enabled by default in its
option table:

```text
statsd-enabled = true
statsd-host    = api.datadoghq.com
statsd-prefix  = acr.nexxen
```

No Datadog API key is present in the extracted tree, so whether it emits
depends on a key supplied at runtime. Treat it as a potential third-party
metric sink, not a proven active one.

### 3.3 What the vendor admits

The English Alphonso opt-in text shipped on the TV
(`/var/local/hamservice/eng_gbr.json`, `base_text`) says:

> Alphonso Video AI collects information about the TV shows,
> advertisements and other content from this TV, as well as unique,
> resettable identifiers associated with the TV and its IP address. This
> data is used to power the Enhanced Viewing features. This data may be
> shared with data partners who append additional information, and may be
> aggregated into anonymous reports and **sold to Alphonso's clients**. The
> data may also be used to deliver more relevant advertising on this TV
> and **other devices that share the same IP address**.

The VIDAA Enhanced Viewing Service privacy notice
(`/mnt/tvroot/opt/euladpp/document/pn4_enhance/pn4_enhance_0_b-his_l-eng.html`)
is even more explicit:

> If you have opted-in to enabling the EV Service on your Device, the EV
> Service will **continuously analyze audio from any onscreen content**
> accessed or displayed on your Device at that moment, including content
> from any set-top-boxes, media players, gaming consoles, over the air
> broadcast, or other audiovisual sources playing through your Device.

> ... the ACR service included in this device will **irreversibly encode
> the analyzed audio signals**, and may also irreversibly encode video
> signals, from onscreen Content into hashed digital signatures
> ("Digital-print"), which are transferred from this device to the ACR
> service for further processing ...

> This ACR process will associate the data with the **public wide area
> network ("WAN") IP Address** used by this device ... The ACR service also
> generates a random number to associate with this device, which ... would
> be called a **"SmartTV Identifier"**.

> ... produce aggregate, de-identified analytics ... to deliver more
> relevant advertising on **other devices that share the IP address** of
> this Device ...

> If you do opt-in, and your Device supports it, EV Service will be
> activated automatically once EV Service is available in your location.
> ... even if the EV Service is not currently available in your location,
> the automatic content recognition ("ACR") service included in this
> device will irreversibly encode the analyzed audio signals ...

The UI also has the string:

> Enable Market Research and Personalized Ads (Requires ACR to be enabled)

and points at `https://nexxen.com/acr-data-partners/`.

### 3.4 ACR consent events are themselves telemetry

The ACR UI reports its own state to the run-log service under vendor
`Tremor`:

- `200316` — ACR capable: `builtin:<n>,killswitch:<n>,sdk:<...>,init:<...>`
- `200317` — ACR active: status
- `200318` — ACR AIAQ/AIPQ status
- `200319` — ACR consent event with `stepid`:
  - `0` qualified device
  - `1` close by ACR privacy-notice refuse
  - `2` open by user switch
  - `3` close by user switch
  - `4` open by opt-in accept
  - `5` close by promotion refuse
  - `6` close by promotion skip
  - `7` open by ACR privacy-notice accept
  - `8` close by promotion "select later"

So even opting out / skipping the prompt has a code path that reports the
interaction. The local counter
`ACR.ACRLogReportRecord` was `{"time":"2026-11-2","count":0}` on this unit,
so it did not accumulate here.

### 3.5 State on this unit: OFF

This is the important part. The ACR machinery is installed, but **not
active**:

- `/var/local/kilby/kireg-kilby0.dat`:

  ```text
  DIR 0x08 acr/
    KEY 0x04 aiaqpq 0
    KEY 0x04 anonymize 0
    DIR 0x08 picture/
      KEY 0x04 adapt 0
    /DIR
    KEY 0x04 recommendation 0
    DIR 0x08 sound/
      KEY 0x04 adapt 0
    /DIR
    KEY 0x04 switch 0
  ```

- `/APPS/euladpp/current/eula_dpp_status.ini`:

  ```ini
  eula             = 1
  dpp_general      = 1
  pn4_enhance      = 0      # Enhanced Viewing / ACR off
  pn5_improvement  = -1     # improvement program disabled
  pn8_advertisement = -1    # personalised ads disabled
  pn9_datasharing  = 0      # data sharing off
  ```

- Cobalt storage
  (`/var/local/hisenseUI/cobalt_home/.starboard...storage`):

  ```text
  ACR.FirstOptOutRecord  = 20338     # 2025-09-07 if a day count
  ACR.OptOutRecord       = 20338
  ACR.ReminderTimes      = "3"
  ACR.ACRReminderMeLaterTime = 20413 # 2025-11-21
  ACR.ACRLogReportRecord = {"time":"2026-11-2","count":0}
  ```

- `HamService` is still running (PID 4111) because it also does DLNA, and
  the ACR SDK is loaded, but the switch is `0` and the opt-out record is
  present. **Do not describe this unit as currently fingerprinting
  viewing.**

The EULA default template is also interesting:

```ini
# /mnt/tvroot/opt/euladpp/config/dpp_list_default.ini
default = Y,Y,N,Y,N,Y
#          eula,dpp,pn4,pn5,pn8,pn9
```

That is: EULA yes, general privacy yes, **ACR no**, improvement yes, ads
no, data sharing yes by default. The app-specific file
(`dpp_list_by_app.ini`) has `acr = 207,Y,Y,Y,N,N,N`, i.e. the ACR app can
carry its own consent. The per-unit status file is the authority.

---

## 4. Voice assistants

### 4.1 Alexa AVS metrics

`avsservice` ships the Alexa AVS SDK. Its metric libraries
(`libMetricRecorder.so`, `libMetricsDelegate.so`) include:

- `MetricRecorder::recordMetric`
- `MetricsDelegate::addCloudWatchMetric`
- `MetricsDelegate::addRedshiftMetric`

That is Amazon-side operational telemetry (CloudWatch/Redshift), on top of
whatever the Alexa service sends to Amazon for voice requests.

### 4.2 Hisense voice-service telemetry

`libhi_cloud_openapi.so` has a `voiceservice` family:

```text
/voiceservice/reportdeviceinfo
/voiceservice/reportdevinfo
/voiceservice/reportstate
/voiceservice/reporttraitstate
```

The query strings carry:

```text
mac, applist, deviceName, vsAbility, clientIdAVS,
deviceSerialNumberAVS, productIdAVS, inputlist,
GSEnable, VSEnable, languageId, hsv,
brandCode, capabilityCode, featureCode, statCode
```

Base domain in the SDK: `api.hismarttv.com`. These are voice-device
inventory/state/trait reports, not ACR viewing data.

Always-running voice pieces in the live snapshot include
`AlexaNativeAppService`, `voiceservice`, `ignition` (Amazon VSK), and
`avsservice`. **On this unit these are now bind-stubbed** (2026-11-03), so
the voice telemetry path is off; the `api.hismarttv.com` voice endpoint is
also sinkholed.

---

## 5. Ads / monetization

`adService.js` (and `apiService.js`, `payService.js`) reference:

```text
https://rpt-mntz.vidaahub.com
```

Ad objects carry `impressionURLTemplates`, `clickTrackingURLTemplates`,
`clickThroughURLTemplate`, `clickThroughContent`, `viewability`,
`adId`, `adType`, `adReport`, `impression_rounds`, `clickValid`.

The OTA/EPG SDK also has ad-strategy calls:

```text
/cgi-bin/epg_index.fcgi?action=getadstrategy&adinfo=
/cgi-bin/epg_index.fcgi?action=getadlinkinfo&adlinkid=
```

This is standard ad delivery/measurement. The privacy link is ACR:
`pn8_advertisement` is the "Market Research and Personalized Ads" switch
and requires ACR. On this unit `pn8_advertisement = -1` and
`pn9_datasharing = 0`, so the personalised-ad path is not consented.

---

## 6. OTA telemetry

### 6.1 Version check

`ota_upgrade` runs from `start-ota_upgrade.sh` on every boot and on manual
check. It sends a device fingerprint to `/upgrade/check_version`:

- software version, machine type, soft material number
- country, zip codes, TV brand, GUI language code
- full HW MAC (`HW_GetFullHWMac`)
- `capabilityCode`, `osStage`
- eMMC life (`slc`, `mlc`)
- `hotfixVersion` (`/OAD/hotfixVersion.ini`)
- `currentTimestamp`, `currentVersion`, `checkMode`
- `deviceExtInfoStr` (JSON: `capabilityCode`, `osStage`, `emmcLife`,
  `mlcLife`, `hotfixVersion`, `currentTimestamp`)
- `dvcRsv`, `httpmode`, `languageCode`, `postCode`, `statCode`,
  `brandCode`, `sourceType=1`
- `msgId=66`, `msgType=256`, `msgVersion=513`, `version=11.0`, `format=0`,
  `accessToken`

### 6.2 Event report

`report_upgrade_event` is a separate call per event (search result,
download status, EULA state, failure, success). It sends
`deviceExtInfoStr`, `eventCode`, `accessToken`, `version`, `sourceType`,
`languageId`, and writes:

```text
/var/local/upgrade/report_upgrade_event_result_data.xml
```

`ota_upgrade` has `desensitize_mac` / `mask_str` helpers; the OTA docs say
MACs are anonymised before send. The run-log service does not do this
(see §2.4).

### 6.3 State on this unit

- `/var/local/upgrade/report_upgrade_event_result_data.xml`:
  `<resultCode>0</resultCode><desc>success</desc>` (2026-08-14).
- `/var/local/upgrade/check_version_result_data.xml`:
  `<errorCode>205001</errorCode><errorDesc>no match upgrade rule...</errorDesc>`
  (2026-10-31).
- `/OAD/AppUpgradeSwitch.json` for `GBR`: `upgradeFlag = "0"` — OTA is
  administratively off for this country.

---

## 7. Local collection and LAN exposure (not cloud)

These are worth separating from the cloud path. They are real collection
capabilities, but the evidence does **not** show automatic cloud upload.

### 7.1 DAB command surface

`/var/local/dab/security/cmd_list_dab.json` whitelists:

```text
/operations/list
/applications/list
/applications/launch
/applications/launch-with-content
/applications/get-state
/applications/exit
/system/restart
/system/settings/list
/system/settings/set
/system/settings/get
/output/image
/device-telemetry/start
/device-telemetry/stop
/device-telemetry/metrics
/app-telemetry/start
/app-telemetry/stop
/app-telemetry/metrics
/input/key-press
/input/key/list
/input/long-key-press
/health-check/get
/device/info
/version
/messages
/voice/list
/voice/set
/voice/send-text
/voice/send-audio
/list-devices
/add-device
/remove-device
```

`/output/image` is a screenshot command. The TV also has a running
`capture` service (PID 2881) and `systemserver` screenshot action
(`kilby.sl2.action.system.capture.screen`, `captureScreenShot`,
`screenshotDir`). The support shell has a "Screenshot to USB/OAD" menu
(item 16). No evidence this is uploaded to the cloud.

### 7.2 MQTT / DAB transport

`/mnt/tvroot/opt/iot/mosquitto/mosquitto.conf`:

```text
#Until now, only DAB connect to this port
listener 1883
allow_anonymous true
plugin /opt/iot/mosquitto/lib/libmosq_extra_security.so
```

There is a DAB auth/whitelist plugin (`libdab_auth_client.so`,
`DabTopicWhite`) in front. Treat `1883` as a **LAN-facing DAB surface**
with vendor auth, not an open internet port. The shipped firewall is
supposed to keep low ports off the WAN, but the live `iptables` capture
only shows the active `FIREWALL_IN_EULAON` chain (contents not captured),
so external reachability was not re-tested here.

### 7.3 Support bundle (`getlog` / `getlog-pii`)

`/mnt/tvroot/usrlocal/scripts/getlog` and `getlog-pii` collect a large
static list, including:

- `/var/tvservice/deviceserial/deviceId`
- `/var/local/kilby/kireg-kilby0.dat`, `kireg-kilby1.dat`
- `/serialdata/common/serials.ini`
- `/var/local/timerlist.db3`
- `/APPS/hisenseUI_applications/UI/kidsmode/kidsSettings.json`
- `/APPS/hisenseUI_shared_data/adsBlacklist`
- `/APPS/hisenseUI_shared_data/staticParams.json`
- `/APPS/hisenseUI_applications/hisenseUI/KillSwitch.json`
- `/var/local/etc/resolv.conf`, `/tmp/wpas.scan`
- `/var/local/log.phoenix*`
- `/OAD/factorykey.log`, `/OAD/factory_1.log`
- `kireg` (all Kilby properties, including ACR switch and account IDs)

`/var/local/timerlist.db3` schema has `parentalLockPIN` and `CAMLockPIN`
columns. On this unit the table has **0 rows**, so no PIN is present — but
the collector does not redact those columns.

The PII scrubber (`replace-pii.sh`) only redacts:

- IPv6 addresses
- IPv4 addresses
- MAC addresses (replaces the first two octets, keeps the last four)
- `[SENSITIVE]` tagged fields
- Wi-Fi SSIDs (keeps the last 2 chars)

It does **not** redact device serial, device ID, kids settings, app lists,
or the Kilby property dump. The zip is made with `enctool log`, and
`enctool`/`dectool` embed zip passwords (see [50-security-review.md](50-security-review.md)).
So the support bundle is obfuscated, not confidential against anyone with
the firmware.

### 7.4 Audio / screen / media capture tools

- `getaudiolog`: sets `dump_es=1`, `dump_pcm=1`,
  `pcm_capture=1 data=spk`, `dump_hdmi_npcm=1`, `dump_spdif_npcm=1` in
  `/proc/utopia_mdb/audio`, sleeps 10 s, then packages the dump. This can
  capture speaker PCM. It is a manual support script, not a boot service.
- `screenshot`: `/mnt/tvroot/usrlocal/bin/screenshot`; used by the support
  menu. The DAB whitelist separately exposes `/output/image`, and the TV
  has a capture service, but the two were not traced end-to-end here.
- `capture`: `/mnt/tvroot/usrlocal/bin/capture`, links
  `libcapture-screen.so`, `libcapture-biz.so`, `libscreen-magnification.so`.
  It is the frame-buffer capture service; no cloud endpoint strings.
- `mdharvester`: scans local/USB/DLNA media into
  `/var/run/granary.db3` (titles, artists, albums, genres, playtime,
  thumbnails, resume positions). It talks to `masman` over local TCP; no
  cloud upload strings.
- `write_stat`: traces block writes, maps inode → file, and emits CSV. A
  debug/flash-wear tool, not a network reporter.
- `syslogviewer` / `rotatelog`: local syslog capture (`/var/log/log.txt`,
  `/var/log/messages`, `/var/local/log.txt`) and rotation to flash/USB.
- `log2usb`: configured in `/etc/init.d/common/init_log2usb.rc`, but the
  `/bin/log2usb` binary is **absent** in the backup — vestigial config.

### 7.5 Phoenix crash report

`/var/local/log.phoenix.report` is a Node diagnostic report written by the
phoenix runtime. It contains:

- command line, Node/glibc versions, arch
- JavaScript stack and heap summary
- native stack, libuv handles, workers
- **environment variables** (paths, model, `SYS_SERIAL_NUMBER=IDTV`,
  `NODE_OPTIONS`, CA bundle paths)
- user limits, loaded shared objects (including
  `libhi_logreport_agent.so`, `libhi_cloud_openapi.so`)

This particular dump has no cloud token in the environment block, but it
is a rich local file and it is on the `getlog` collection list.

---

## 8. What is actually on/off on this unit

| Item | Value | Interpretation |
|---|---|---|
| `eula` | `1` | EULA accepted |
| `dpp_general` | `1` | general privacy policy accepted |
| `pn4_enhance` | `0` | Enhanced Viewing / ACR **off** |
| `pn5_improvement` | `-1` | improvement program disabled |
| `pn8_advertisement` | `-1` | personalised ads disabled |
| `pn9_datasharing` | `0` | data sharing off |
| `acr/switch` | `0` | ACR fingerprinting **off** |
| ACR opt-out | `20338` (2025-09-07) | user opted out on install day |
| ACR reminders | `3` | prompted three times |
| ACR log report | `count 0` on 2026-11-02 | no ACR event batch accumulated |
| `hi_logreport_service` | running, PID 2764 | general diagnostics daemon live |
| log policy | cached 2026-10-31, `policySeq` 2026-11-02 | alive, policy processed |
| OTA check | `205001 no match upgrade rule` | no update served to GBR |
| OTA event report | `resultCode 0` (2026-08-14) | event reporting worked |
| DAB debug | `/var/local/dab_debug` absent | DAB tool not enabled |
| PVR timers | 0 rows | no parental/CAM PIN in the DB |
| `HamService` | running, PID 4111 | ACR host + DLNA; ACR switch is 0 |
| Voice | stubbed | `voiceservice`, `AlexaNativeAppService`, `ignition`, launchers blocked |

**Conclusion:** this unit is **not** currently sending ACR viewing data. It
is running the general diagnostic run-log service and the OTA checker, and
the ACR stack is installed but opted out. The "juicy" material is the
capability, the cloud policy, and the local collection surface — not an
active viewing-data feed from this TV.

---

## 9. The juicy / nefarious list (ranked)

1. **ACR can fingerprint any on-screen audio, not just the tuner.** The
   privacy notice says "any set-top-boxes, media players, gaming consoles,
   over the air broadcast, or other audiovisual sources". That is a
   whole-room / whole-input viewing meter, not a TV-channel feature.
2. **The vendor says the data may be sold and used for ads on other
   devices sharing the IP.** The Alphonso opt-in text is explicit about
   "sold to Alphonso's clients" and "other devices that share the same IP
   address".
3. **The log service collects process tables and `/proc` details.** On a
   CPU/memory/flash alert it tars `ps`, `top`, `/proc/*/cmdline`,
   `/proc/*/status`, `/proc/*/statm`, `df`, `ls -l /var/local`, and
   `du -sd1 /var/local`. That is a system inventory, not a stack trace.
4. **Coredumps and backtraces are uploaded.** `TvCoredumpThread` /
   `TvBacktraceThread` push `/var/crash/` files and emit event `010001`.
   Process memory can contain tokens and user data.
5. **The cloud can define a "self-defined log" job with a URL.** The
   parser accepts `url`, `logger`, `playStat`, `maxCount`, `size`; the
   thread tars debug files and uploads them. This is a remote collection
   primitive, even if unused here.
6. **The log service sends the raw MAC while OTA masks it.** `ota_upgrade`
   has `desensitize_mac`/`mask_str`; `hi_logreport_service` has neither and
   formats `&MAC=%s`. Inconsistent privacy engineering.
7. **ACR consent interactions are telemetry.** Codes `200316`–`200319`
   report capability, active state, AIAQ/AIPQ, and the exact opt-in/opt-out
   step (`stepid 0`–`8`) under vendor `Tremor`.
8. **The ACR notice says it will encode even if the service is not
   available in your region** (if you opted in). That is a "collect now,
   monetise later" posture.
9. **The support bundle's PII scrubber is narrow.** It redacts IP/MAC/SSID
   but collects device ID, kids settings, ad blacklist, static params,
   KillSwitch config, Kilby properties, and a timer DB with PIN columns.
   The zip password is embedded in `enctool`.
10. **DAB exposes a screenshot and input-injection API.** The whitelist
    includes `/output/image`, `/input/key-press`,
    `/applications/launch`, `/voice/send-audio`, and
    `/device-telemetry/*`. MQTT `1883` is `allow_anonymous true` behind a
    vendor plugin. LAN-only in principle; worth probing if you care about
    local trust.
11. **Local capture tools are one menu away.** `getaudiolog` can dump
    speaker PCM for 10 seconds; `screenshot` writes the current frame to
    USB/OAD; `capture` is always running. No cloud upload evidence, but
    the capability is there.
12. **`log.phoenix.report` dumps environment variables and loaded libs.**
    It is collected by the support bundle and is a useful map of the
    runtime.

---

## 10. What it does **not** do / open questions

- **ACR is not active on this unit.** `acr/switch=0`, `pn4_enhance=0`,
  opt-out records present. Do not claim otherwise.
- **No evidence of automatic cloud screenshot upload.** `capture` /
  `screenshot` are local; the DAB `/output/image` path is local/LAN.
- **No proof of a specific log batch upload.** We have policy fetch,
  `policySeq`, and OTA event success. The per-run queues are in `/tmp` and
  were not preserved in the backup.
- **`mdharvester` is local.** It writes `/var/run/granary.db3`; no cloud
  endpoint strings. It indexes local/USB/DLNA media metadata.
- **DAB `1883` is LAN-facing, plugin-gated.** The live `iptables` capture
  did not include the active `FIREWALL_IN_EULAON` rule contents, so WAN
  reachability was not re-tested.
- **No Datadog key in the tree.** The ACR SDK has the Datadog option path
  enabled by default, but no `NEXN_STATSD_API_KEY` / `DD_API_KEY` was
  found.
- **No hardcoded cloud tokens.** Auth is anonymous device auth with a
  cached token; no static API key was found in the log-service strings.
- **`log2usb` is configured but absent.** The init script exists; the
  binary does not.
- **`pn5_improvement=-1` and `pn9_datasharing=0`** mean the improvement
  and data-sharing programmes are off. The log service's gate string
  names EULA/PP, so general diagnostics remain eligible; the improvement
  flag is a separate observer.

---

## 11. Verify it yourself

Extract the relevant snapshots:

```sh
B=<EMMC_BACKUP>
mkdir -p /tmp/tvtel
tar --use-compress-program=unzstd -xf $B/fs/mnt_tvroot.tar.zst -C /tmp/tvtel
tar --use-compress-program=unzstd -xf $B/fs/APPS.tar.zst -C /tmp/tvtel
tar --use-compress-program=unzstd -xf $B/fs/var_local.tar.zst -C /tmp/tvtel
```

Policy and endpoints:

```sh
cat /tmp/tvtel/APPS/logservice/xml/report_policy_xml_file.xml
cat /tmp/tvtel/APPS/logservice/policySeq
eu-strings -n 5 /tmp/tvtel/mnt/tvroot/usrlocal/bin/hi_logreport_service \
  | grep -E 'ter-jrnl|exc-jrnl|get_log_policy|deviceStatus|reportTag|MAC='
```

Collection script:

```sh
cat /tmp/tvtel/mnt/tvroot/usrlocal/scripts/logreport_gatherlog.sh
cat /tmp/tvtel/mnt/tvroot/usrlocal/scripts/start-logreport.sh
cat /tmp/tvtel/mnt/tvroot/usrlocal/etc/apm/application-config.ini \
  | sed -n '/\[hi_logreport_service\]/,/^$/p'
```

Consent / ACR state:

```sh
cat /tmp/tvtel/APPS/euladpp/current/eula_dpp_status.ini
grep -A10 'DIR 0x08 acr/' /tmp/tvtel/var_local/var/local/kilby/kireg-kilby0.dat
eu-strings -n 3 /tmp/tvtel/var_local/var/local/hisenseUI/cobalt_home/.starboard.*.storage \
  | grep -A1 'ACR\.'
```

ACR vendor text:

```sh
jq -r '.base_text' /tmp/tvtel/var_local/var/local/hamservice/eng_gbr.json
sed 's/<[^>]*>//g' \
  /tmp/tvtel/mnt/tvroot/opt/euladpp/document/pn4_enhance/pn4_enhance_0_b-his_l-eng.html \
  | head -40
```

ACR SDK options / endpoints:

```sh
eu-strings -n 5 /tmp/tvtel/mnt/tvroot/usrlocal/bin/HamService \
  | grep -E 'acr\.unruly|registration-url|supported-url|fp-send-interval|statsd|NEXN_INPUT'
```

DAB surface:

```sh
cat /tmp/tvtel/var_local/var/local/dab/security/cmd_list_dab.json
grep -n -A6 'listener 1883' /tmp/tvtel/mnt/tvroot/opt/iot/mosquitto/mosquitto.conf
```

Support bundle:

```sh
grep -n -E 'deviceId|kidsSettings|timerlist|adsBlacklist|KillSwitch' \
  /tmp/tvtel/mnt/tvroot/usrlocal/scripts/getlog-pii
cat /tmp/tvtel/mnt/tvroot/usrlocal/scripts/replace-pii.sh
```

---

## 12. If you want it quiet (optional)

**Applied on this unit 2026-11-03:** `hi_logreport_service` and both
launchers are bind-stubbed by `the stub applier`; `ter-jrnl`, `exc-jrnl`,
`rpt-mntz`, `acr.unruly.co`, `api.datadoghq.com` and `api.hismarttv.com`
are sinkholed in `/data/etc2/hosts`; ACR is pinned with `acr.switch=0` and
`acr.kill.switch=1`; voice is stubbed (`voiceservice`,
`AlexaNativeAppService`, `ignition`, `avs_start.sh`, `alexa_start.sh`).
The OTA guard was already active.

- **Leave Enhanced Viewing off.** Keep `pn4_enhance=0` and
  `acr/switch=0`; do not accept the ACR prompt. This is the big one.
- Keep `pn5_improvement`, `pn8_advertisement`, `pn9_datasharing` off.
- Block the telemetry domains at DNS/firewall if you do not need vendor
  services:
  `ter-jrnl.vidaahub.com`, `exc-jrnl.vidaahub.com`,
  `rpt-mntz.vidaahub.com`, `acr.unruly.co`, `api.datadoghq.com`,
  `api.hismarttv.com`.
- Note that blocking `*.vidaahub.com` broadly also breaks app store, EPG,
  recommendations, and OTA.
- The log service is kept alive by APM (`isKeepAlive=true`,
  5-second restart). Freezing it needs the same bind/stub discipline used
  for `ota_upgrade` (the author's private notes describe it), not a simple
  `kill`.
- Watch DNS for `*-jrnl.vidaahub.com` and `acr.unruly.co`; those are the
  clearest "telemetry is talking" signals.
- Do not rely on the "improvement" switch alone; the EULA/DPP-general
  gate is the one the log service names in its stop path.
