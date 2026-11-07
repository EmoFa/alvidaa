# Publication policy

What this repository publishes, what it deliberately does not, and how a
contributor can tell the difference. Read this before adding a guide or a
payload.

The short version: **findings are public, payloads are not shipped, and every
guide says which is which.**

## What is published

- **Findings.** What a build does, what was measured, what failed, and the
  evidence for each claim. Architecture, not incantation.
- **Evidence labels.** Every result is marked *verified* (observed on a
  project device), *community reported* (an owner's report, not reproduced
  here), *hypothesis* (proposed, untested) or *untested*. A claim without a
  device observation stays labelled as a claim.
- **Teardown paths.** How to undo whatever a guide describes. Reversibility is
  the design law, and a guide without a rollback is incomplete.
- **Tooling that is safe to run.** Read-only probes, the launcher, the CLI, the
  deploy scripts. These are the things a normal owner needs.

## What is not published

- **Working payloads.** No IPK that runs a `postinst` as root, no boot-hook
  script that arms a unit, no exploit chain packaged as a one-command tool.
  The guides describe what the chain rests on; they do not ship the chain.
- **Key material.** No private keys, no tokens, no device certificates, no
  keystore passwords. `server/keys/` is gitignored and stays that way.
- **Vendor binaries.** No redistributed vendor executables or libraries.
  `scripts/check.sh` scans for them and fails the build.
- **Unit identifiers.** MAC addresses, serials, LAN addresses and device codes
  are placeholders in published text.

## The line, stated by a contributor

The clearest formulation came from a contributor whose material arrived as a
private bundle, and it is worth quoting rather than paraphrasing:

> The docs in this bundle are publishable on their own. The payload and the
> exact chain are what shorten the window.

That is the boundary this repository uses. A guide may say *what* property of
the firmware makes a chain possible. It may not hand over the artefact that
executes it.

## Why this line

Two reasons, and they point the same way.

**It is the honest one.** The information is already public once a guide
describes the mechanism; the marginal risk of the payload is real, and the
marginal benefit to an owner who wants to understand their own TV is zero.

**It is the useful one.** A guide written to the boundary is a better guide.
It explains the shape of the failure, which is what transfers to the next
model, instead of a sequence of commands that only works on one build.

## Verification labels

| Label | Means |
| --- | --- |
| **verified** | observed on a project device, with the evidence recorded |
| **community reported** | an owner reported it; not independently reproduced here |
| **hypothesis** | proposed from static analysis; never run |
| **untested** | no result yet. Say so rather than implying success |

A failed observation applies only to the route and device that were tested. It
does not mean the build is secure, and it does not mean the route is closed
everywhere.

## Vendor coordination

A vulnerability report covering the 2024+ VIDAA firmware issues described in
this repository was sent to Hisense/VIDAA Product Security
(`VIDAASecurity@vidaa.com`, `report@connectlife.io`) on **2026-10-29**, and the
repository was published in parallel rather than waiting on a 90-day window.

**Vendor response, 2026-11-07 — `VIDAA-PSIRT-2026-005`:**

- The **root path** (unauthenticated localhost bridge, `../` traversal,
  `/var/local` boot hook) was **reported to them earlier** and is **already
  fixed on most devices**, with an OTA fix coming for the remaining ones
  including the reference `50A51HUV`.
- The **MQTT authentication issue** (client-certificate identity gate and the
  dynamic credential derivation) is **new to them** and under investigation.

They asked for this repository to be taken private and for the exploitation
detail to be removed from the write-up until the fixes ship. The repository
stays public, for the reasons in [SECURITY.md](../SECURITY.md): the material
has been public since 2026-10-29, is forked and mirrored, and making it private
now would remove the one maintained copy without removing the information.

The write-up carries the vendor's position at the top of the page, and the
exploitation detail was toned down to findings rather than removed, on the
boundary described above.

Status will be annotated here as fixes land and as other models report in.

## If you are a vendor

Open an issue or reach the repository owner. Findings will be annotated as
patched as firmware catches up, and any advisory or CVE reference will be
linked from the affected guide.

## If you are contributing

Write the guide to the boundary:

1. State the fingerprint (model, firmware, SoC, region) exactly as the TV
   reports it.
2. Describe the chain at the level of *what property makes it possible*.
3. Label every claim with one of the four evidence labels.
4. Include the teardown path.
5. Fill in the **What this guide includes and leaves out** section, so the next
   reader knows what you withheld and why.

The template is [docs/models/_TEMPLATE.md](models/_TEMPLATE.md).
