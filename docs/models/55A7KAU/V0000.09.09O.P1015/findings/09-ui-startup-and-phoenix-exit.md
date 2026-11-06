# UI startup credentials and Phoenix CLI exit-status trap

After the user confirmed cold-boot recovery to stock Home, investigated the
restart failure without stopping the working engine or changing launcher files.

## Boot path on this firmware

`/usr/local/scripts/start-hisense.sh:290` invokes:

```text
/usr/local/bin/secure_exec hisenseUI /opt/hisenseUI/startgui.sh
```

`startgui.sh` sets HOME to the Cobalt storage directory, DB_HOME to
`/var/tvservice`, the vendor library search path, changes cwd to
`/opt/hisenseUI`, and backgrounds `./bin/hisenseUI` with the file-origin
index URL. It does not constitute a restart supervisor.

The actual AU policy is `/usr/local/etc/apm/application-config-eu-au.ini`.
Its launcher stanza does say `isKeepAlive=true` and
`restore_time_when_crash=10`, but the first trial demonstrated that those
settings alone are not evidence of a working SIGKILL/respawn path.

The recovered engine was PID 357, parent 1, UID/GID 311, with
`CapEff: 0000000000a05000`. A harmless probe through `secure_exec hisenseUI`
running BusyBox shell and reading its own `/proc/self/status` reproduced the
engine's UID/GID, supplementary group list, and effective capabilities exactly.
No second UI instance was launched. This establishes the credential wrapper,
not successful engine restart or visible recovery.

The engine also inherits platform environment variables beyond those set in
`startgui.sh` (including SYS_*, LINUX_*, FUSION_* and CFG_SYS_INI). A restart
experiment must capture the live process environment privately and pass it
through the wrapper rather than use the sparse SSH environment. Do not source
`/etc/profile`, start the engine directly as root, or launch a duplicate engine.
Vendor scripts/config/binary inspected here are saved in gitignored
`firmware/55a7kau-09.09o/native-analysis/`.

## Phoenix ignores process.exitCode on normal shutdown

While checking the newly disabled trial script, it printed the expected
assertion but SSH returned zero. Isolated probes confirmed:

| Phoenix code | SSH exit status |
| --- | --- |
| `process.exitCode = 7` | 0 |
| `process.exit(7)` | 7 |

The trial manager now uses explicit `process.exit(1)` in its top-level error
handler. Both `start` and `worker` were then verified on the TV to reject with
exit 1 before any deployment work. This is important for future preflight
scripts: exitCode assignment alone cannot make shell callers fail reliably.

## Safety changes

- Local and staged `native-trial.cjs` reject start/worker. Real-device apply is
  blocked, and recovery refuses to stop a running engine.
- Preserved the original staged script as `native-trial.cjs.before-disable`;
  it is historical evidence, **not a usable trial command**.
- The local launcher now carries a yellow `ALVIDAA — NATIVE TEST N02` heading
  to distinguish it from the pre-existing browser launcher. It was not deployed.
- Updated the guide to withdraw the previous trial-ready claim.

The initial investigation did not change stock launcher files, watcher
configuration, origin storage, root persistence or PC server state. It only
replaced the staged trial manager.

## Supervised stock-only restart: success

The operator then explicitly authorized the stock-only test and watched the TV.
`tools/launcher-host/stock-ui-restart.cjs` was staged and byte-verified. It:

1. Verified original index, shared 537.js and launcher SHA-256 hashes.
2. Captured the live engine environment in memory (not printed or persisted).
3. Saved the original watcher config under
   `/var/local/alvidaa/stock-restart-check/config.original`, disabled the watcher,
   and waited seven seconds for pending bounce activity to settle.
4. Sent SIGTERM to the identified stock engine. It used no SIGKILL fallback
   and would have refused to launch a duplicate if the old engine remained.
5. Relaunched using `secure_exec hisenseUI /opt/hisenseUI/startgui.sh` with the
   captured environment, then verified matching credentials and stable identity.

Stock engine PID changed **357 → 3268**. The user pressed Home and confirmed
**Stock Home works**, including arrow-key focus, while the watcher was off.
After the observation interval the script restored the watcher config; host
readback confirmed it matched the original byte-for-byte. All three original
UI hashes still matched. No launcher bundle or cache was modified by this test.

This validates the stock-only lifecycle path on this boot. It does not prove
custom rendering, automatic recovery from a wedged JS runtime, or cold-boot
safety. The native trial remains disabled until both apply and restore paths
are adapted to explicit, checked relaunch instead of assumed APM respawn.

Four additional local tests cover the restart helper: explicit launch,
avoiding duplicates on platform respawn, refusing forced kill on SIGTERM
failure, credential mismatch, missing/duplicate engines and early exit.
