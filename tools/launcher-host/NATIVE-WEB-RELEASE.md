# Private Free My TV web release

This builds the pinned web UI plus compatibility adapters for the **55A7KAU
V0000.09.09O.P1015**. It is not a generic VIDAA installer or a claim of completed
parity. See the [acceptance gates](../../docs/launcher/FREE-MY-TV-WEB-PARITY.md)
and [completion evidence and remaining gates](../../docs/models/55A7KAU/V0000.09.09O.P1015/findings/18-web-port-completion.md).

## Reproduce the artifact

Run from the repository root. Use the original, private stock launcher backup,
not the currently modified launcher. Asset generation requires the packages in
`requirements-web-assets.txt` and `rsvg-convert`; do not overwrite existing assets.

```sh
python3 tools/launcher-host/build-native-web-assets.py firmware/my-native-web-assets
(cd tools/launcher-host/native-image && \
  GOOS=linux GOARCH=arm GOARM=7 CGO_ENABLED=0 \
  go build -trimpath -ldflags='-s -w' -o ../../../firmware/native-image-armv7 .)
python3 tools/launcher-host/package-native-web.py \
  firmware/55a7kau-09.09o/native-analysis/launcher-app.js \
  firmware/my-native-web-assets firmware/native-image-armv7 \
  firmware/native-web-release.tar.gz
```

The packager verifies upstream/asset hashes and the original firmware hash,
rejects non-ARM helpers and existing outputs, and writes a mode-0600 deterministic
archive. It contains vendor-derived code and **must not be published**.

Archive layout:

- `runtime/`: root-owned private runtime, helper, compiled candidate and licenses;
  directories 0700, files 0600, executable helper 0755.
- `assets/<asset-id>/`: root-owned public Cobalt assets, directories 0755 and
  files 0644. The candidate embeds this content-addressed asset ID.
- `RELEASE.json`: every payload's size and SHA-256, upstream revision and candidate
  hash. No credential files, environment snapshots or device state are included.

The real build was reproduced twice with identical archive bytes and all members
verified. Separate fixture tests require neither firmware nor real credentials:

```sh
python3 tools/launcher-host/test_native_web_package.py
```

## Deployment boundaries

`native-web-release.cjs` coordinates upgrades and rollback for the existing
configured native Home, and provides stock-Home/feed-hook teardown. **The new
coordinator has offline tests only; its TV lifecycle trial is still pending.**
It does not provision root, pair a new TV, install initial credentials or configure
a first boot hook. Those remain the explicit existing setup recipes.

Do not extract over active TV paths. Keep the [Home controller](NATIVE-LAUNCHER.md),
original backups and working recovery candidate. Never replace origin storage or
vendor read-only partitions. Check free space and `/var/local` state first.
Only use a locally built, reviewed archive: its hashes detect corruption, not an
untrusted publisher. Firmware-derived archives stay private. Private descendant
modes do not repair the existing vendor `/var/local` ancestor (303:303, mode 0777):
its rename/trust limitation remains. Do not describe this as a privilege sandbox.

The current trial uses:

- Private runtime: `/var/local/alvidaa/native-web-v3/`.
- Public assets/media: `/APPS/channelA/hisenseUI/var/local/free-my-tv/`.
- Public file IPC: `/APPS/free-my-tv/`, owned by the existing Phoenix UID/GID 314.
- Private TMDB token: `/var/local/alvidaa/server/keys/free-my-tv.json`, root-owned
  mode 0600. It is separately provisioned, never part of an archive or URL.

The native `storeAppIcon` path is a vendor symlink. Preserve it; the image worker
resolves it and confines reads to the canonical icon directory.

## Guarded release commands

On the owned TV, unpack the private archive into a new root-owned directory
**outside** `/var/local/alvidaa/native-web-v3/`, with mode 0700. Preserve its file
modes. Do not run these commands while another session is changing Home, and do
not run them while the operator has asked for the TV to remain undisturbed.

Use the vendor Node runtime (the `verify` command also runs on a workstation):

```sh
export LD_LIBRARY_PATH=/lib:/usr/local/lib:/basic/lib
NODE=/opt/pkgs/tv.vidaa.app.phoenix/bin/phoenix
STAGE=/var/local/alvidaa/web-release-staging
CTL="$STAGE/runtime/native-web-release.cjs"
"$NODE" "$CTL" verify "$STAGE"
# Inspect Home and its controller state first; supply the hash you reviewed.
"$NODE" "$CTL" apply "$STAGE" '<reviewed-current-home-sha256>'
```

Apply requires the existing native Home and feed boot hook to be installed and
unmodified. It checks shared firmware, candidate syntax, package contents,
ownership and free-space headroom before changing the runtime. It retains exact
runtime bytes/modes and a self-contained recovery controller/helper, stops only
the owned feed, holds its inherited kernel lock and uses the existing Home lock
and stopped-engine update. A failed update or failed new worker startup rolls
back; a failed recovery does **not** restart a mixed runtime. The previously
stopped/running feed state is preserved on rollback.

The printed journal lives under
`/var/local/alvidaa/native-home/web-releases/release-*`. Retain it. To roll back,
even if the live runtime was damaged or the original staging directory removed:

```sh
JOURNAL='<printed-recovery-journal>'
"$NODE" "$JOURNAL/control/native-web-release.cjs" rollback "$JOURNAL"
```

Concurrent Home/runtime changes are refused rather than overwritten. The
coordinator does not provide a cross-filesystem power-cut-atomic swap or automatic
boot-time recovery; an interrupted update may require this explicit rollback.
Do not delete its journal or use a later release's journal for an earlier failure.

To stop the feed, remove only its owned boot fragment and restore stock Home:

```sh
"$NODE" "$CTL" uninstall
```

Teardown retains root/SSH provisioning, credentials in `server/keys/`, origin
storage, cached media, assets and recovery backups. It deliberately does not
recursively delete directories. Teardown also refuses concurrent changes; if it
fails, inspect the existing Home and boot journals before proceeding. Reinstalling
after stock teardown uses the existing Home/boot setup recipes, not `apply` on an
unconfigured baseline.

## Feed lifecycle and boot recovery

Run these only through root SSH, with the vendor Node runtime and its libraries:

```sh
LD_LIBRARY_PATH=/lib:/usr/local/lib:/basic/lib \
  /opt/pkgs/tv.vidaa.app.phoenix/bin/phoenix \
  /var/local/alvidaa/native-web-v3/native-web-service.cjs status
```

Replace `status` with `start` or `stop` as needed. Duplicate starts retain one
kernel-locked worker. Stop verifies process ownership. Restoring a non-web Home
also makes the worker exit; cached media and preferences remain intact.

The boot fragment is added only to the existing retired-bridge root installer:

```sh
python3 tools/launcher-host/patch-native-feed-bootstrap.py \
  firmware/private-installer.original.ipk firmware/private-installer.feed.ipk
```

After staging that private IPK and the checked runtime, the root-local
`native-web-boot.cjs apply <candidate-ipk> <current-installer-sha256>` validates
that only its owned fragment changed and journals the original before replacing
`/APPS/installer.ipk`. `native-web-boot.cjs restore` restores its exact original
bytes and metadata, refusing concurrent edits. The first backup is retained
across reinstallations. These operations were exercised on the TV without
rebooting or running the complete root installer.

The original root payload, SSH setup, blocklist and older phone-home section are
unchanged. **The older phone-home section starts an unauthenticated reverse-shell
retry loop**, not just a notification. The launcher does not need it, but stopping
the PC listener did not retire it. Independently verify root SSH after cold boot
before separately retiring this recovery channel; do not invalidate the feed
journal with an ad-hoc installer edit. No new listener or MQTT session is
introduced by this port. The boot entry is configured and manually tested;
cold-boot, standby and playback/blocklist-collateral acceptance remain pending.
