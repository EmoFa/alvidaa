# 55A7KAU (internal model 55U66GAVT) — V0000.09.09O.P1015

- **Model:** 55A7KAU (sticker, retail) — firmware reports 55U66GAVT (internal/mainboard name)
- **Country:** AUS (Hisense_GetCountryCode), SSDP region=6, Hisense_GetRegion=EM_C
- **Firmware:** V0000.09.09O.P1015
- **SoC:** MTK9602
- **Region:** AU (AUS)
- **VIDAA OS:** U09.09
- **Browser:** Chromium 111 "odin"
- **Reported by:** owner (this session)

## Root chain (verified 2026-11-06)

Same family as the [100U7Q](../../100U7Q/V0000.09.60I.Q0813/README.md) and
[75UR9S](../../75UR9S/V0000.09.60W.Q0624/README.md) superwatch chains, with
`09.09O`-specific constants measured on this unit:

```
TV browser page (fetcher FaaS, wss://localhost:9888)
  └─ vowOS.service.syncExecute("basic/fetcher", {api:"fetchFile", args:…})
       └─ downloads placed as uid 314:
            /APPS/pkgs/tv.vidaa.jsservice.basic/CHA/functions/fetch/sw2.js
            /APPS/installer.ipk
  └─ POST https://localhost:9888/function/basic/fetch/sw2
       body {"list":["<sid>:53:<sid>;/APPS/installer.ipk;re.installer;"]}
       └─ superwatch_server (root) → /usr/local/scripts/ipk_install.sh
```

**Boot persistence** is the `re_sshd` serviceList autostart service, which
re-arms dropbear at every cold boot with an offline re-arm path — the same
mechanism the 75UR9S guide documents, verified here on 2026-11-06.

Evidence, with the source of every claim, is in [EVIDENCE.md](EVIDENCE.md);
the phase-by-phase chain is in
[findings/02-root-ssh.md](findings/02-root-ssh.md) and the read-only recon in
[findings/01-recon-ladder.md](findings/01-recon-ladder.md).

**Two generation deltas worth knowing**: the broker validates the client-cert
CA at the TLS layer (a self-signed cert fails the handshake, unlike the
50A51HUV where refusal came at MQTT CONNECT), and MQTT CONNECT needs a
colon-formatted TV MAC — the colonless form from the SSDP descriptor returns
rc 135 on all four profiles.
