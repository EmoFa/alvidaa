# <MODEL> / <FIRMWARE> — <one-line summary of what was achieved> (<SoC>, <region>)

**Status:** <what is verified, on what date, and what is not. One or two
sentences. If nothing is verified, say that instead of implying progress.>

> **Applies to `<MODEL>` (<SoC>, VIDAA `<version>`, region `<region>`) running
> `<FIRMWARE>`, build date `<date>`.** Say here how narrow the claim is. If the
> same build ships on other models, name them and say whether they were
> tested.

> **Contributed by [@handle](https://github.com/handle).** How the material
> arrived (own device, community report, private bundle) and what was adapted.

## What the chain rests on

The properties of this build that make the result possible, in dependency
order. Architecture level — what is true of the firmware, not the sequence of
commands that exploits it.

1. **<Property>.** What it is, and why it matters.
2. **<Property>.** Same.
3. **<Property>.** Same.

If the chain is the same family as another model's, say so and link it. If it
differs, say where.

## What was measured

A table is usually the clearest form. Every row needs a label from
[the publication policy](https://github.com/carteakey/alvidaa/blob/main/docs/DISCLOSURE.md#verification-labels).

| Claim | Evidence | Source |
| --- | --- | --- |
| <what> | verified / community reported / hypothesis / untested | <how you know> |

## What this guide includes and leaves out

Required section. The point is that the reader knows what was withheld and
why, rather than wondering whether the guide is incomplete or you are.

| Included | Left out |
| --- | --- |
| the fingerprint and firmware constants | working payloads |
| the chain at the architecture level | the exact command sequence |
| the evidence for each claim | key material, tokens, certificates |
| the teardown path | vendor binaries |

Say in one sentence why the line falls where it does for this guide.

## Teardown

How to undo everything. If a step cannot be undone, say so plainly and say
what the residual state is.

## Open items

What is still unknown, untested, or worth trying next. A guide with no open
items is usually a guide that stopped looking.

## Cross-reference

- Related guides: <links>
- Method catalogue: [EXPLOITS.md](https://github.com/carteakey/alvidaa/blob/main/docs/research/EXPLOITS.md)
- Publication policy: [DISCLOSURE.md](https://github.com/carteakey/alvidaa/blob/main/docs/DISCLOSURE.md)
