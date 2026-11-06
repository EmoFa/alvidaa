# First controlled native launcher module trial

The user authorized running the supervised trial. No prior native-stage or
native-trial directory existed. Uploaded the trial manager and launcher to
`/var/local/alvidaa/native-stage/` and verified both uploads byte-for-byte.

Preflight passed: pinned stock hashes matched, Cobalt PID 347 was present,
bridge MQTT was connected, and the existing Home watcher was enabled.

Started the detached trial worker (PID 7347). State reported `active`; its
log recorded `ACTIVE 2026-11-06T11:08:04.294Z` (TV clock). The worker is set to
restore after 180 seconds. The operator was instructed not to reboot and to
report rendering/input behavior. A separate read-only host monitor polls for
restoration and compares restored files against the backups.

The worker subsequently recorded `RESTORED 2026-11-06T11:11:04.719Z`.
Readback SHA-256 verification matched the original launcher and bridge config.
The original watcher configuration (enabled, app Home) was restored.

The user reported seeing the new launcher before the trial had started.
This does not establish native rendering: the prior enabled watcher could
have launched the existing Odin/browser Home app. Disabling the watcher
prevents new bounces but does not close an already-open browser. The next
read-only check returned bridge state `fake_sleep_0` and no process executable
matching hisenseUI/odin; the visible state and power state need clarification.
No native-rendering success is claimed. A subsequent trial needs a verified
stock/native starting view, a unique visible build marker, and process/state
observation during the test rather than merely after it.

## Black screen after rollback: engine restart assumption failed

The user then clarified that the TV was on but black and that they had tried
to restart it. SSH remained accessible; uptime was 5024 seconds, so no kernel
reboot had occurred at that check. Original launcher/config hashes still
matched and both original JS cache directories were back in place. Process
inspection found apmbond, svcmgr, superwatch and browser processes, but no
hisenseUI/startgui process. Browser executables are named `browser`, not
necessarily `odin`, so the earlier exe-name filter was insufficient.

The trial manager's assumption that APM would respawn hisenseUI after SIGKILL
was not validated and did not produce an observed running engine. File/cache
rollback succeeded; visible UI recovery did not. The trial must not be run
again using this restart strategy. After a genuine cold power cycle the user
confirmed that stock Home returned. Subsequent read-only inspection found a
running hisenseUI process and reset uptime. See [09](09-ui-startup-and-phoenix-exit.md)
for the startup-wrapper investigation and disabling the failed trial path.
