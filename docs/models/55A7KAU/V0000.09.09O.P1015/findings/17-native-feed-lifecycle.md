# Native feed lifecycle and boot integration

Scope: owned 55A7KAU, V0000.09.09O.P1015. This is lifecycle work for the
[pinned web UI trial](16-web-runtime-and-feed-cache.md), not proof of perfect
parity or unattended cold boot. The operator is unavailable: no standby, reboot,
mains-power, microphone or audible-accessibility test is authorized in this pass.

## Implementation and local verification

- `native-web-service.cjs` starts the existing worker through the kernel-lock
  helper. Concurrent starts converge on one worker. Status checks the exact
  executable/script identity and required arguments; stop refuses foreign PID
  records and signals only a worker-owned process group.
- The worker watches Home's file identity/metadata, rereading it only when changed.
  Replacing web Home with stock or the previous adaptation makes it stop itself.
  Cached snapshots/media remain available; it never rewrites Home or preferences.
- Image helper processes are cancelled when their media owner stops. Worker CLI
  failure paths now use explicit exit, consistent with the Phoenix exit trap
  already documented in findings 09.
- `patch-native-feed-bootstrap.py` adds only `native-feed-boot.sh` to the already
  retired-bridge installer. Root payload bytes, other control files and control
  ownership/permissions are checked independently by `native-web-boot.cjs`.
- The boot controller retains a mode-0600 original and a recovery journal before
  atomically replacing `/APPS/installer.ipk`. It refuses changed hashes and
  unknown adjacent edits. Exact restoration, repeated application/restoration,
  corrupted journals and concurrent edits are covered by local tests.
- Boot entry failure leaves cached Home usable. It does not reintroduce a
  listener, MQTT client or PC dependency. The old installer phone-home section is
  deliberately unchanged and remains a separate audit item.

## Read-only device checks before deployment

The current web Home still hashes to
`355b7d8b692ffa92091bf63966c0ec4daf27ea9352678f6ec0d837079a27726b`.
The retired-bridge installer hashes to
`42f85336352fb174d51272dcbd61f66226bfc029ee9c3d02a8f92f5c464c29be`,
matching its retained local copy. The existing worker was PID 14340. Native Node
exposes `AbortController`.

Some trial runtime files retained the host archive's UID/GID 1000. Their parent
release directory is already root-owned mode 0700, but deployment must normalize
owned runtime files to root ownership before enabling autostart. Service startup
now rejects foreign-owned or group/world-writable worker/helper files. It does
not change vendor ownership: Phoenix is UID/GID 314 mode 0550; Home is UID/GID
305 mode 0664.

**Trust limitation:** vendor `/var/local` is UID/GID 303 mode 0777, without the
sticky bit. `/var/local/alvidaa` is root-owned mode 0751; release and credential
subdirectories are root-owned mode 0700. Private descendant permissions alone
cannot prevent an actor with write access to that ancestor from renaming the
whole tree. This work does not change vendor directory permissions or claim to
repair the existing root bootstrap's broader trust boundary. Keys remain in the
private `server/keys/` tree and are not copied into browser assets or logs.

## On-TV deployment and rollback exercise

The private release's 1,819 entries were normalized to root ownership, directories
0700, ordinary files 0600 and the image helper 0755. Original metadata is retained
in its private `ownership-before.json`. Cobalt's separate 1,728 public asset files
were checked afterward: all remained world-readable, with no hardlinks to the
private tree.

The first service preflight rejected the firmware's icon directory because
`storeAppIcon` is actually a symlink to
`/APPS/hisenseUI_applications/UI/launcher/cache`. Cached Home stayed intact while
the worker was stopped. The service now follows that specific vendor directory
alias, without changing it; the media layer still enforces canonical containment.
The service tests now use the same symlink arrangement. The corrected service
started PID 15977; repeated starts retained that same process and process group.
Previous worker source bytes are retained under private `feed-before-lifecycle/`.

The boot hook was installed, restored byte-for-byte, then installed again on the
TV. Its isolated shell entry was executed successfully; the complete root
installer was **not** run. Original IPK bytes and metadata remain under
`/var/local/alvidaa/native-home/web-feed-boot/`. The installed IPK hashes to
`5f6f1d2043080867678aeea92d687b92df85a8bc37d99286c8d6a31da2872857`.
Restoration preserves the original UID/GID 314 and mode 0644.

Afterward, snapshot PID matched service PID 15977, with 96 image mappings, 230
media mappings, zero image failures, 47 apps and recognized Australia/Brisbane
location. No credential value was printed. The Home journal remained installed,
with the same engine PID 15139: no UI restart or power-state change was requested.

Autostart is now **configured and its isolated entry tested**, not cold-boot
verified. Local tests and manual service startup cannot establish reboot, standby,
voice, audible accessibility or complete visual/behavioral parity.

## Reproducibility and additional checks

`package-native-web.py` built the real private release twice with identical bytes:
1,804 payload files, asset ID `49e13fbfa4c41725e0cd`, and the same installed Home
candidate hash. All payload hashes, root archive ownership, scoped modes and
absence of credential paths were checked. Its fixture tests also cover traversal,
symlinks, accidental public output and overwrite refusal. See the
[release recipe](../../../../../tools/launcher-host/NATIVE-WEB-RELEASE.md).

Four additional adapter tests verify legacy theme/ordered-favorite migration,
empty favorites, malformed legacy data, independent web preference persistence
and isolation from vendor keys. They do not substitute for device persistence
across power cycles.

The seven deterministic desktop views were rerendered after the clock/scoping
fixes. Mean RGB differences were 0.001–0.061; pixels differing by more than 16 in
any channel were 0.001–0.042%. These are **no-picks fixtures**, not live-card or
Cobalt pixel-parity evidence. Images remain local at
`/tmp/fmtv-lifecycle-visual/`. A separate passive HAL capture at
`/tmp/fmtv-feed-lifecycle.jpg` shows the movie-art screensaver and clock on the TV.
