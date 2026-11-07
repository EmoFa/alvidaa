# Model Guide: Hisense 43A5FE (VIDAA OS U07.51)

This document covers research findings, verified root execution, and the debloating/ad-blocking architecture for the **Hisense 43A5FE**.

For the standard repository setup and launcher instructions, please refer to the [Main alvidaa README](../../../../README.md).

---

## 🛡️ Peace of Mind: Safety & DRM

* **Widevine L1:** 100% intact. Hardware keystores, TEE, and Verified Boot (`verifiedbootstate=green`, `device_state=locked`) remain active. Netflix, Disney+, and Prime Video continue to stream in native 4K/HDR.
* **Firmware Integrity:** No custom firmware flashing or bootloader modifications. System partitions (`/`, `/usr`, `/opt`) remain read-only (`dm-verity` enforcing).
* **Teardown & Reversibility:** Deleting `/var/local/otaTest.sh` or selecting **Restore Factory Defaults** from the TV settings completely reverts the unit to factory state.

---

## 📺 System Profile

* **Model:** Hisense 43A5FE (`FamilyName = hisense_mt5870_linuxDB`)
* **Firmware Version:** `V0010.09.09A.P0930` (Build date: 2025-09-30)
* **Kernel:** Linux version 4.19.79+ (Linaro GCC 4.9.3) SMP PREEMPT armv7l
* **SoC:** MediaTek MTK9602 (`ProductMaker = mediatek`)
* **OS / SDK:** VIDAA OS U07.51 (SDK 6.1.2)
* **Browser:** Chromium 111.0.0.0 "odin" (armv7l)
* **Partitions:** Read-write `/APPS` (partition `/dev/mmcblk0p41`), `/var/local`, `/data`.

---

## 🔑 Operator Notes & Pairing Nuances

When pairing via `server/pair.py`:
* The upstream repository script polls for an ephemeral file at `server/keys/.pin`.
* Because the TV displays an on-screen 4-digit PIN that rotates every 60 seconds, an interactive console prompt (`input()`) in a background thread is recommended for manual operators to submit the PIN immediately without manual file creation.

---

## 🚀 Verified Root Execution & Boot Hook

1. **Write Primitive:**  
   Browser path traversal (`HiUtils_createRequest('fileWrite', ...)`) resolves against `/APPS/`. Content must be passed in `writedata` (mode 6) to escape to `/var/local/otaTest.sh`. Other keys (`data`, `content`) return `ERR_INVALID_ARG_TYPE`.

2. **Privilege Escalation:**  
   The vendor startup script (`/etc/rc.local` / `start-hisense.sh`) runs `/var/local/otaTest.sh` as `root` (uid 0) on every cold boot if present.

3. **Firewall Watchdog:**  
   Vendor scripts (`firewall-init-subrule.sh`) drop incoming connections on debug ports shortly after boot. The hook uses `/bin/toybox_selinux nc` (port 2323) with a background `iptables` watchdog loop:
   ```sh
   /bin/toybox_selinux setsid /bin/sh -c "while :; do /usr/local/bin/iptables -C INPUT -p tcp --dport 2323 -j ACCEPT 2>/dev/null || /usr/local/bin/iptables -I INPUT 1 -p tcp --dport 2323 -j ACCEPT; sleep 20; done" > /dev/null 2>&1 &
   /bin/toybox_selinux setsid /bin/toybox_selinux nc -p 2323 -L /bin/sh -i > /var/local/nc.out 2>&1 &
   ```
   Connecting via `ncat <TV_IP> 2323` provides an immediate interactive root shell (`uid=0`).

---

## 📦 On-Device Node.js Runtime

The firmware bundles Node.js v20 as part of the Phoenix framework:
* **Binary:** `/opt/pkgs/tv.vidaa.app.phoenix/bin/phoenix` (Node.js v20.9.0)
* **Required Library Path:**
  ```sh
  LD_LIBRARY_PATH=/usr/local/lib:/basic/lib:/vendor/lib:/lib:/system/lib /opt/pkgs/tv.vidaa.app.phoenix/bin/phoenix -v
  # Outputs: v20.9.0
  ```

---

## 🧹 Debloating & Telemetry Neutralization

### 1. Hiding Bloatware from the Home Screen
The launcher hides preset apps via:  
`/APPS/hisenseUI_shared_data/launcher/hiddenApps.json`

To inspect the 62 pre-installed applications and their IDs:
```sh
LD_LIBRARY_PATH=/usr/local/lib:/basic/lib /opt/pkgs/tv.vidaa.app.phoenix/bin/phoenix -e 'const d = JSON.parse(require("fs").readFileSync("/APPS/hisenseUI_shared_data/launcher/allAppsInfo.txt", "utf8")); d.AppInfo.forEach((a, i) => console.log(`${i+1}. [ID: ${a.appId}] ${a.AppName}`));'
```
Adding an application's `appId` into `hiddenApps.json` hides the corresponding tile cleanly from the home screen without package removal.

### 2. Blocking Ad Servers & DoH Bypass
Hisense hardcodes DNS-over-HTTPS queries to Google (`8.8.8.8:443`) for `*.vidaahub.com` to bypass local DNS resolvers (Pi-hole/AdGuard).

To block DoH evasion and drop telemetry:
```sh
/usr/local/bin/iptables -I OUTPUT 1 -d 8.8.8.8,8.8.4.4 -p tcp --dport 443 -j REJECT
```
Mapped ad and telemetry endpoints in `/APPS/domain/domain_list.json`:
* `rsc-ads.vidaahub.com` (banner ads)
* `evt-eu.vidaahub.com` (telemetry/analytics)
* `traffic-ui.vidaahub.com` (UI click tracker)

---

## 🔄 Reversal & Teardown

To revert all modifications:
```sh
rm -f /var/local/otaTest.sh /var/local/otaTest.log
```
Or perform a **Factory Reset** directly from the TV user interface.
