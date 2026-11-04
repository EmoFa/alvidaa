# Prior art and prior-run lessons

This page records what earlier local investigations established, what they
corrected, and what remains open. It is a provenance note, not a tutorial. Raw
run logs are intentionally not part of this repository; this page keeps only
the durable findings and the limits that follow from them.

## 1. OTA is per-device authenticated

The Hisense/VIDAA OTA API is not a public firmware directory. The prior work
reconstructed the request/signature primitives and established:

- The API host and the upgrade host are separate services. The request format
  includes a version, a language id, a device-reserved field, a brand/country
  block, and an access token.
- A signed request uses a vendor public key. The signature is reproducible, but
  a valid request still needs a device-specific token and fields that are not
  set inside the public libraries.
- `check_version` returned `errorCode 100013` ("accessToken is lost") without a
  token, and `errorCode 100014` ("parameter error: deviceId") when a token was
  present but the device-id mechanism was wrong.
- The OTA check for the 2025 target returned `205001` ("no match upgrade
  rule"), meaning the service had no matching upgrade rule for that device.
  That is not proof that no firmware exists anywhere; it is proof that this
  authenticated path did not offer one.
- The legacy local path (a device-side download-server address file) was empty.

Consequence for the public tool: OTA is **not** part of the default catalog.
The public `tools/ota` component may contain request/signature primitives, but
it must not ship a device token, a private key, an `appKey`/`appSecret` value,
or a login flow.

The underlying static-analysis notes are not shipped.

## 2. The public Hisense page is not a complete firmware index

The 100U7Q investigation established a concrete, limited fact:

- `https://www.hisense.es/descargas-firmware/100u7q/` returned HTTP 200 with a
  **0-byte HTTP body**.
- The rendered DOM of that response is the 39-byte skeleton
  `<html><head></head><body></body></html>`.
- Seven tested U7Q slugs returned the same zero-byte body.
- These results are `empty`, not `absent`. The cause (model not listed,
  template/CMS problem, geo/UA filtering, or late hydration) was not decided.

Correction: an earlier note said "0 bytes" and another said "39-byte skeleton".
Both are right at different layers. The public documentation must state both.

## 3. A populated model page proves the filename pattern

The prior run's shell transcript cache preserved a populated model page for
`m7000`:

- `https://www.hisense.es/descargas-firmware/m7000/` returned HTTP 200.
- The title was `Descarga de firmware - Hisense España`.
- The page contained direct links to
  `HE55M7000UWTSG_pkg_20181127.tar.gz` and
  `HE65M7000UWTSG_pkg_20190123.tar.gz` under
  `wp-content/uploads/firmwares/`.

This confirms the file URL pattern
`https://www.hisense.es/wp-content/uploads/firmwares/<MODEL>_pkg_<YYYYMMDD>.tar.gz`
for this site. It does not prove that every region, model, or route follows it.
An earlier pass classified the pattern and the `m7000` page as hypotheses
because the workspace itself contained no HTML dump. The transcript cache
upgraded both to **CONFIRMED via prior-run transcript**.

The same evidence established:

- the index route is singular (`/descarga-firmware/`), the model route is plural
  (`/descargas-firmware/<slug>/`);
- `/wp-content/uploads/firmwares/` returns 403, so directory listing is not an
  enumeration path;
- regional probes returned 403 (`co.uk`), 404 (`it`, `fr`), 000 (`de`), and 200
  with a JavaScript app (`com.au`, `usa`) that did not list the EU model.

Consequence: the crawler must support both route families, extract direct
anchors, and treat `empty`/`403`/`000` as distinct outcomes.

## 4. The three-primitive root vector (reference device)

On the HE40E5600FFWTS, the live-confirmed chain was:

1. **Browser root** — `hisense_browser` ran as UID/GID 0 with the full
   capability set, a single process, and no seccomp/`NoNewPrivs`.
2. **USB write primitive** — the `IsSubDentry` whitelist used `realpath` plus a
   prefix check. A dangling symlink on an ext4 USB filesystem made `realpath`
   fail, and `HiBrowser.File.download` followed the symlink to create a
   root-owned file outside the whitelist.
3. **Loader shadow** — `libtvsysinfo.so` was a direct `NEEDED` entry, and the
   first writable `LD_LIBRARY_PATH` position was the same directory. A shadow
   library with an appended `DT_INIT` ran as root on browser restart.

Then a root command loop, key-only Dropbear SSH, a PTY workaround, and a
`HamService` boot wrapper provided persistence.

Important limits:

- This was validated live on the reference device, not on the 2025 target.
- The 2025 target has a 32-bit ARM userland, closes the network DevTools
  channel, and does not share the browser UID, whitelist or library load order
  (measured: the app/browser context runs as uid 314, not root).
- The final report must keep "confirmed on the reference device" and
  "confirmed on the target" separate. The target now has its own verified
  chain (`../../100u7q/`) which uses none of the mechanisms above.

## 5. Negative results worth keeping

- Debug ports 9223/9224 were not reachable on the 2025 target; the browser JS
  channel over the network was gone.
- No ADB service was exposed.
- The public model page was empty for the tested U7Q slugs.
- Paid mirrors were not usable: one required sign-in/payment, another returned
  403. They are not public sources and must not be presented as such.
- A whole-disk filesystem without a partition table was not mounted by the
  reference TV; a partition table was required.
- FAT32 cannot represent symlinks, so it cannot exercise the symlink bypass.
- A password-auth Dropbear build was not available; key-only auth was used.

## 6. Lessons for the public release

1. **Separate discovery from proof.** A URL is not a file, and a 200 is not a
   complete page.
2. **Separate `empty` from `absent`.** The most common mistake in the prior
   notes was treating a zero-byte page as "no firmware".
3. **Separate the reference device from the target.** Hardware and firmware
   conclusions do not transfer without a new validation.
4. **Do not ship credentials to make a demo work.** The OTA path is
   per-device; the public tool must stay key-free.
5. **Keep the negative results.** They prevent a future run from repeating a
   dead end and they make the coverage report honest.
6. **Publish metadata, not firmware.** The catalog records links and facts; it
   does not redistribute vendor images.

## 7. Open questions

- Does any region other than `hisense.es` share the same WordPress template and
  expose direct firmware links?
- Do the WordPress media API and sitemap expose files that the model pages do
  not link?
- What is the exact cause of the empty U7Q pages: no listing, template failure,
  geo/UA filtering, or late hydration?
- Does the 2025 target still run its browser as root, and does the USB/library
  chain still exist?
- Will a free official firmware image for the 2025 target be published?
