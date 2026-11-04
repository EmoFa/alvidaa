'use strict';
const net = require('net');
const fs = require('fs');
function one(payload) {
    return new Promise((resolve) => {
        let chunks = [];
        let done = false;
        const finish = (extra) => {
            if (done) return; done = true;
            const buf = Buffer.concat(chunks);
            resolve(Object.assign({ payload: payload.slice(0, 60), len: buf.length, text: buf.toString('utf8').slice(0, 120), hex: buf.toString('hex').slice(0, 60) }, extra || {}));
        };
        const c = net.createConnection('/var/run/superwatch_socket', () => {
            const b = Buffer.from(payload, 'utf8');
            const h = Buffer.alloc(4); h.writeUInt32LE(b.length, 0);
            c.write(Buffer.concat([h, b]));
        });
        c.setTimeout(15000);
        c.on('data', d => chunks.push(d));
        c.on('end', () => finish());
        c.on('timeout', () => { c.destroy(); finish({ timeout: true }); });
        c.on('error', e => finish({ err: String(e) }));
    });
}
module.exports = async function (args) {
    const list = (args && args.list) || [];
    const out = [];
    for (const p of list) out.push(await one(p));
    try { fs.writeFileSync('/tmp/sw2_result.json', JSON.stringify(out)); } catch (e) {}
    return { result: true, out };
};
