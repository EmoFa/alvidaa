# Safety

## The short version

> Rooting, replacing libraries, and flashing firmware can brick the TV. A wrong
> library can stop the browser from starting; a bad partition write can leave a
> black screen; power loss during a write can make the device unbootable.
>
> Work only on a device you own and are authorized to modify. Test on a
> non-primary TV. Back up first. Keep a rollback path. No warranty.

## Before you start

- Confirm the exact model, firmware version, SoC and architecture. A helper
  built for one device family is not portable to another.
- Read the tool's README and the relevant device notes. Do not run a script
  because it has a familiar name.
- Keep the original firmware image and a copy of every file you replace.
- Record the current partition layout and mount options.
- Make sure you can recover without the TV's UI: serial console, recovery
  image, or a vendor-supported reinstall path.
- Use a non-primary TV for the first run. Do not experiment on the household's
  only screen.

## Power and storage

- Do not interrupt power during a write, a flash, or a first boot after a
  change.
- Do not remove the USB stick while the TV is writing to it.
- Use a reliable power supply and a USB device you can afford to lose.
- A whole-disk filesystem without a partition table may not be mounted by the
  TV. A partition table and the expected filesystem are part of the procedure;
  do not guess.
- Keep the rollback files on a separate device, not only on the TV.

## Root and persistence

- Root access is not the goal by itself. Every persistence layer (boot hook,
  bind mount, replaced library, SSH service) is another way to fail the next
  boot.
- Install one layer at a time and verify after each step.
- Keep a root command channel and a rollback script available before you
  install a boot hook.
- Do not touch `/etc/shadow` or password authentication if key-only access is
  enough. A locked-out SSH service is recoverable; a broken boot is not always.
- If a library shadow is part of the procedure, keep the original library and a
  tested way to remove the shadow.

## Network and remote access

- This repository does not include remote login flows, credential guessing, or
  vendor account access.
- Do not expose an SSH service or a debug service to the internet.
- Bind services to the local network only, and only while you are working.
- Do not reuse a personal SSH key. Generate a dedicated key for the device and
  remove it when you are done.
- A TV that is reachable from the internet is a TV that someone else can reach.

## Firmware and OTA

- A public firmware link is not a guarantee that the image matches your model.
  Verify the model code and package date before flashing.
- Do not flash an image from a paid mirror, a random forum attachment, or a
  file whose hash you cannot check.
- OTA endpoints may be per-device authenticated. Do not try to bypass that
  authentication; use a vendor-supported update path.
- Do not downgrade unless you have a confirmed recovery path. Some devices
  enforce anti-rollback.

## If it goes wrong

1. Stop. Do not repeatedly power-cycle a device that is mid-write.
2. Disconnect network and USB only after the write has finished or failed
   cleanly.
3. Try the documented recovery path for the exact model.
4. Restore the original library, partition image, or firmware.
5. If the device does not boot, document what changed and seek vendor or
   community recovery help with redacted logs.

## Legal and ethical

- Modify only hardware you own or are explicitly authorized to modify.
- Do not use these tools to access a device you do not own, to bypass a
  paywall, or to redistribute vendor firmware.
- Respect the licenses of third-party components. See `LICENSE` and the
  upstream projects.
