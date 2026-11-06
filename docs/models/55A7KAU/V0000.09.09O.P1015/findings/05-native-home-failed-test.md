# Native home replacement: failed boot test

The user reported a black screen after reboot with an inline DOM launcher in
`/APPS/channelA/hisenseUI/index.html` and a patch to `static/js/537.js`
changing `render:e=>e(E)}).$mount("#app")` to
`render:e=>e("div")}).$mount("#app")`.

This configuration did not establish a working replacement home. The cause
has not been isolated. Claims that the root component could be bypassed while
retaining all required platform behavior were premature. Stock module code
still loads under this approach; preventing one render is not proof that all
stock UI work or overhead is eliminated.

## Recovery

Root SSH on port 8008 remained reachable. Restored both files with `cp -p`
from `/var/local/alvidaa/backup/channelA-index.html.orig` and
`/var/local/alvidaa/backup/537.js.orig`. Read back both originals and restored
files over SSH and compared their bytes on the host: matches, respectively
493 and 141044 bytes. The user subsequently rebooted and confirmed that
stock Home returned.

TV `cmp` was unavailable and BusyBox lacked the `sha256sum` applet; those
verification attempts failed before host-side byte comparison succeeded.

No cache or storage was deleted during recovery. Earlier commands using
`rm -rf /var/local/hisenseUI/cobalt_home/*` did not match hidden entries such
as `.cache`; earlier statements that the compiled cache had definitely been
cleared were unsupported. Do not repeat broad storage deletion as a cache fix.
