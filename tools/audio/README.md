# Audio probe — does the TV's capture PCM carry the final mix?

Status: **run 2026-11-06 — the answer is no.** The capture lane is dead on
this model; see [the result](#result-2026-11-06-the-capture-lane-is-dead-on-this-model)
below. Written 2026-11-05, measured on the 50A51HUV (MTK9602,
09.01O.P0813) the next morning.

## Why

The `snapcast` question (see `TODO.md`) and the librespot task (issue #19) both
depend on one unknown: can a userspace process on this TV get audio in and out
of the ALSA stack, and does it get *what the room hears*?

What is known:

- **Kernel side exists.** Card 0 is `MStar-MAD`; five `mad_pcm` devices each
  report `playback 1 : capture 1`, and `/dev/snd/pcmC0D0{c,p}` are present
  (`root:mi 660`).
- **Userspace side is thin but not absent.** No `aplay`/`amixer`, nothing in
  busybox, and no ALSA headers — but `/vendor/lib/libasound.so.2.0.0` **is**
  on the device (703 KB, armhf, glibc 2.31). So a dynamically linked armhf
  binary can use the TV's own library; no static ALSA build required.
- **No compiler on the TV.** Cross-compile on the host.

## What the probe answers

`probe_alsa_capture.c` opens a capture PCM, sets S16_LE / 48 kHz / stereo via
`snd_pcm_set_params`, reads N seconds, and prints peak and RMS. Three outcomes:

| Result | Meaning |
| --- | --- |
| real audio | the tap carries a signal — snapcast/librespot are viable |
| digital silence | nothing playing, or this PCM is not the output mix |
| constant value | the device opened but carries no signal |

The question that actually matters is subtler than "does it work": if the tap
sits *before* the TV's DSP and volume stage, a streamed copy will not match the
speakers and the multiroom idea is much less useful. Compare the capture's
loudness against the room while changing the TV volume — if the file does not
change, the tap is upstream of the volume control.

## Use

```sh
tools/audio/build.sh                 # zig cc, links the TV's own libasound
tools/audio/capture-probe.sh         # push, capture 3s, pull, clean up
python3 tools/audio/analyse.py /tmp/alvidaa-audio-build/cap.raw
```

`build.sh` pulls `/vendor/lib/libasound.so.2.0.0` from the TV read-only and
links against it with `-target arm-linux-gnueabihf.2.31` to match the device's
glibc. The binary needs `/lib/ld-linux-armhf.so.3` and `libasound.so.2`, both
present.

## Safety

- Writes only to `/tmp` on the TV (tmpfs, gone at reboot) and removes its own
  files.
- Opens a **capture** PCM. On some stacks that can glitch or steal playback —
  run it when nobody is listening.
- No service, hook, or config changes.

## Result (2026-11-06): the capture lane is dead on this model

Measured on the 50A51HUV (MTK9602, 09.01O.P0813), first with the binary as
built (b7d9172), then with the explicit-start / recover-instead-of-bail
variant (1a5cc77):

- `snd_pcm_open("hw:0,0", capture)` succeeds. `snd_pcm_set_params`
  (S16_LE / 48 kHz / stereo) succeeds. `snd_pcm_start` succeeds.
- Then **every `snd_pcm_readi` returns EIO**; `snd_pcm_recover` reports -5
  each time and the probe exits with `frames=0`.
- The reason is visible in the kernel, not in our code: during playback,
  **all ten PCMs report `closed`** in `/proc/asound/card0/pcm*/sub0/status`
  — five `mad_pcm` devices × playback + capture. Tested with audio going
  to an optical (S-PDIF) speaker **and** with the TV's internal speakers.
  Same result both ways.

Conclusion: on this model the TV's audio never enters a userspace ALSA
stream. The `mad_pcm` nodes are the MStar decoder's internal interface, not
the output mix, and nothing on the runtime side ever opens them. EIO is the
correct answer, not a bug — there is no stream to read from.

Consequence: **snapcast and librespot are not viable on this model through
ALSA.** Not a build problem, an architecture one — linking against the
TV's own `libasound` cannot change what the kernel exposes.

The probe and `build.sh` stay in the tree: they are the evidence for this
negative result, and the same experiment may answer differently on another
SoC (the HiSilicon models ship different audio stacks).

## Untested path: audio in the TV browser

One door stays open and is labelled as such. The TV browser (`odin`) is
declared with `--alsa-output-device=default;hw:0,0;...`, so audio played
**in a web page** might open a PCM where a native app does not — the
browser's own audio stack sits between the page and the kernel and can
take a path the media apps skip.

If anyone wants to close this off: play audio in the TV browser (any page
with an `<audio>` element) and sample `/proc/asound/card0/pcm*/sub0/status`
while it plays. If a sub0 flips to `OPEN`/`RUNNING`, the browser lane
exists and the question reopens; `closed` everywhere closes the audio
file for good. Do not assume this one — the native-path probe above was
also written assuming it would work.
