# re_sshd — boot-persistence service (deployed to this TV)

Byte-identical copies of the files deployed on 2026-11-06 (pulled over the
root SSH lane, verified against the TV with `diff`). See the [model README's
Boot persistence section](../README.md#boot-persistence-verified-2026-11-06)
for the full chain, cold-boot evidence, and traps.

| File | Deployed to |
|---|---|
| `index.js` | `/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/services/re_sshd/index.js` |
| `package.json` | `/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/services/re_sshd/package.json` |
| `serviceList.json` | `/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/services/serviceList.json` (pristine copy on the TV: `serviceList.json.pristine`) |

`current -> CHA` is a symlink, so the `current/...` paths resolve to the same
inodes. Redeploy: copy the two service files, replace `serviceList.json`,
reboot (no hot-reload of the list). Teardown: restore
`serviceList.json.pristine`, `rm -r CHA/services/re_sshd`.