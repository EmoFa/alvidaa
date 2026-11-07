# Cobalt capabilities measured for the faithful web port

The operator authorized a brief, reversible Home UI compatibility probe.
Three small probe variants were appended to the working private bundle and
installed through the existing checked update controller. After **each** run,
the original working candidate was reapplied and its SHA256 verified:

`9f121cb6efc5d5ade10812196fbbc5795163e6865206c3aa3dc8e92847d97014`

The probes made no remote-key calls, hardware-setting changes or power cycles.
Temporary host listeners served only the test font/image and collected the
capability report; they stopped after each run. They are not runtime dependencies.
No open-web URLs were loaded into the privileged browser.

## Results

| Capability | Observed result |
| --- | --- |
| Native viewport | 1920 × 1080 |
| `innerHTML` | Created a span with the expected text |
| DOM selectors | Document/element selectors exist; inserted element found by ID |
| Custom event bubbling | Reached the parent listener |
| Rounded corners | Computed longhand radius `20px` |
| Shadows, gradients, blur, transforms | CSS parser/computed-style values accepted |
| CSS mask properties | Empty computed values for both tested spellings |
| Canvas | Element exists, but no `getContext` or `toDataURL` |
| SVG | Element creation alone works; no SVG class/namespace evidence; rendering not established |
| `Intl` / `FontFace` constructors | Absent |
| Original variable Inter font | Downloaded, but test text retained fallback metrics |
| Static Inter instance | Downloaded and produced the exact upstream advance-width metric |
| Image loading | `onload` fired; tested width/height and natural-size properties were absent |
| XHR to package-relative local JS | Failed: status 0, empty body |
| Existing vendor file bridge | HTTP 200, `ret:true`, string result |

Computed CSS acceptance is not a screenshot/pixel-equivalence test. In
particular, the empty shorthand `border-radius` value from the first probe was
**not** proof of unsupported rounding: testing `border-top-left-radius` resolved
that ambiguity. Do not strip effects based on the shorthand result.

## Font workaround is measured, not guessed

The source Inter font has `opsz` and `wght` axes. A static instance at its
original default optical size 14 and weight 400 was generated with fontTools.
The derivative's internal family/name fields were renamed for OFL compliance.

At 40 px, `MMMMWWWWiiii` measured:

- Source font advance widths: **340.9375 px**.
- Cobalt with the static instance: **340.9375 px**.
- Cobalt fallback, and the variable-font test: **307.671875 px**.

This supports generating the required static weights from the actual upstream
font rather than substituting a system font. It does not prove all glyphs,
weights, kerning or rasterization have been visually validated.

A subsequent genuine Chromium web reference measured **323.796875 px** for the
same 40 px string with the variable font and `font-optical-sizing:auto`.
Consequently, simply using the default optical-size-14 static font everywhere
is **not** sufficient for visual parity. Optical sizing and text shaping must
be included in the comparison. An optical-size-32 static instance has an
unshaped advance sum of 322.03125 px; that sum alone does not establish its
rendered width or explain the remaining shaping difference.

The first local HTTP reference attempt mistakenly DNS-blocked `127.0.0.1` as
well as external hosts. Chromium returned exit 0 while reporting a failed
page load and produced no screenshot. Excluding both localhost and 127.0.0.1
fixed the harness. Check the rendered artifact, not just the browser exit code.

## Serverless cache-read path

Cobalt cannot use the tested package-relative file XHR as a data reader, but it
can call the existing vendor endpoint:

```text
POST http://localhost:9009/service/hiutils
{"api":"fileRead","args":{"path":"websdk/Appinfo.json","mode":6}}
```

Only success/type/length were reported, not the file's contents. This establishes
a way to read a bounded, non-secret native feed/asset cache through an existing
vendor service, without adding a launcher HTTP server. The prospective worker
must fetch external data off-browser, write only its own cache namespace, and
never put API keys in browser-readable data. File-writing/cache integration
has not yet been implemented or tested by these read-only probes.

Runtime package bases are `../system-ui` and `../operation-ui`. These resource
paths are not an invitation to change the shared router or load open-web pages.
The current working launcher remains installed while the faithful port is built.
