# 55A7KAU (internal 55U66GAVT) V0000.09.09O.P1015 — modding notes

The launcher lane works end to end on this unit: server on 8765, `/api/open`
loads the page, the TV fetches it and opens `/ws` (101), and the applist
renders with real apps. Pairing succeeds on the `modern` profile with the
2024 `VidaaAppAndroidV01` cert and a colon-formatted TV MAC.

The self-install lane (`Appinfo.json` write) was not exercised here — see the
[55A7KAU root findings](findings/02-root-ssh.md) for what was run, and the
[65U8HAU guide](../../65U8HAU/V0000.06.29X.P0813/README.md) for the
origin-gate behaviour that blocks it on the U6 generation.
