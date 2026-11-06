# Native launcher trial preparation and host cleanup

Status: local tooling implemented and tested; no launcher deployment performed.
Stock Home is still installed. Root bootstrap and on-TV bridge were not modified.

## Read-only TV checks

- Engine `/proc/347/exe` resolved to `/opt/hisenseUI/bin/hisenseUI`.
- The original shared index, shared `537.js`, and operation-ui launcher entry
  matched their recorded SHA-256 hashes. The trial manager pins those hashes.
- Phoenix Node's executable path is
  `/opt/pkgs/tv.vidaa.app.phoenix/bin/phoenix`; it parsed the candidate successfully.
- Bridge `/api/debug` returned HTTP 200 and `mqtt.connected: true` (PID 2253).
- `/var/local/alvidaa/config.json` still has the Home watcher enabled. The
  proposed trial temporarily disables it and restores the original config.

The actual cache paths are under the **hidden** directory
`/var/local/hisenseUI/cobalt_home/.cache/cobalt/`:
`compiled_js` and `uncompiled_js` are separate directories, alongside HTML,
CSS, images and other caches. Origin storage remains a separate
`.starboard.*.storage` file in `cobalt_home`. Earlier wildcard deletion did not
establish that these hidden caches had been invalidated.

## Local trial package

[Guide](../../../../../tools/launcher-host/NATIVE-LAUNCHER.md),
[launcher](../../../../../tools/launcher-host/native-launcher.js), and
[trial manager](../../../../../tools/launcher-host/native-trial.cjs).

The launcher now has connection timeout/retry, SDK diagnostic markers,
rem-based layout, and handled Home-call rejections. The trial manager provides
read-only preflight, private backups with hashes/owners/modes, atomic writes,
narrow JS-cache directory swaps, a detached TV-side worker, a three-minute
monotonic trial deadline, automatic restore, and manual recovery. It refuses
unknown baselines, stale trial directories, corrupt backups or concurrent edits.
15 local tests passed, including the saved vendor module loader and simulated
partial failures/rollback. Engine restart failure attempts to release all
paused processes rather than leaving later processes stopped.

Important: the detached worker survives SSH disconnect, **not reboot/power
loss or SIGKILL**. Engine restart through APM and rendering still need live
validation. No permanent acceptance command exists. Do not reboot during the
trial; wait for restoration, or recover over SSH first. A boot-persistent
rollback mechanism is a prerequisite for a later cold-boot deployment.

## PC-side setup servers

The only remaining matching listener was PID 316015, `python3 server.py 9000`,
with cwd `/home/jackson/alvidaa/tools/u7q/web`. Its cgroup was a tmux session
scope, not a dedicated service. After confirming both command and cwd, sent
SIGTERM to that PID. Both server and its old parent shell exited. A subsequent
listener listing showed no setup server on 9000, 8765 or 8770; remaining
listeners were unrelated Steam/Tailscale services and were left alone.

No matching autostart entries were found in checked user/system systemd units,
user/system desktop autostart, shell startup files, cron locations, Hyprland
configuration or tmux snapshots. The user's tmux restoration service exists,
but `@resurrect-processes` is explicitly `false` both in config and live tmux.
No matching autostart entry needed disabling. This does not remove manual
launch commands from shell history or prevent a future explicit server start.
