"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const { BaseService } = require("@sdk/baseService.js");
const net = require("net");
const fs = require("fs");

const D = "/APPS/.re_sshd";
const MARKER = D + "/boot_marker.txt";
const SOCKET = "/var/run/superwatch_socket";
/* superwatch opkg protocol (same payloads as tools/u7q/web/install.html):
   90 = uninstall, 91 = install; 82/83 = package ids of re.installer.
   The install re-runs postinst as uid 0, which restarts dropbear on 8008. */
const PAYLOADS = [
    "90:83:90;re.installer",
    "91:82:91;/APPS/installer.ipk;re.installer;"
];

function log(msg) {
    try { fs.appendFileSync(MARKER, new Date().toISOString() + " " + msg + "\n"); } catch (e) {}
}

function dropbearRunning() {
    try {
        const pid = parseInt(fs.readFileSync(D + "/dropbear.pid", "utf8").trim(), 10);
        fs.accessSync("/proc/" + pid + "/cmdline");
        return true;
    } catch (e) { return false; }
}

function sendOne(payload) {
    return new Promise((resolve) => {
        let chunks = [];
        const c = net.createConnection(SOCKET, () => {
            const b = Buffer.from(payload, "utf8");
            const h = Buffer.alloc(4); h.writeUInt32LE(b.length, 0);
            c.write(Buffer.concat([h, b]));
        });
        c.setTimeout(15000);
        c.on("data", d => chunks.push(d));
        c.on("end", () => resolve(Buffer.concat(chunks).toString("utf8").slice(0, 120)));
        c.on("timeout", () => { c.destroy(); resolve("TIMEOUT"); });
        c.on("error", e => resolve("ERR " + e.message));
    });
}

async function arm() {
    for (let i = 1; i <= 36; i++) {
        if (dropbearRunning()) { log("dropbear already running"); return; }
        const r1 = await sendOne(PAYLOADS[0]);
        const r2 = await sendOne(PAYLOADS[1]);
        log("attempt " + i + " uninstall=[" + r1 + "] install=[" + r2 + "]");
        await new Promise(r => setTimeout(r, 5000));
        if (dropbearRunning()) { log("ARMED: dropbear up"); return; }
    }
    log("GAVE UP after 36 attempts");
}

class ReSshd extends BaseService {
    constructor(name, dest) { super(name, dest); }
    async start() {
        log("re_sshd start pid=" + process.pid + " uid=" + process.getuid());
        if (dropbearRunning()) { log("dropbear already running"); return; }
        arm().catch(e => log("arm error: " + e));
    }
}
module.exports = ReSshd;
