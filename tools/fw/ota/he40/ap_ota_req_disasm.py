#!/usr/bin/env python3
# AP-OTA-REQ-DISASM: static disassembly of OTA request builder functions in libhisdk.so.
# ARM mode (even entry VAs), no execution, no network. Capstone 5.0.6.
import struct
from capstone import *
from capstone.arm import *

FN = "libhisdk.so"
SHA = "49c8417721348f7931f85cf01d350a8d9fd996face301827a1d520716e19fb0a"
data = open(FN, "rb").read()

# ---- section layout (from readelf) ----
# .text   0x2d38..0x402a8  (off==va)
# .rodata 0x402b0..0x48a18  (off==va)
# .got    0x51350..0x51570  (off = va - 0x8000)
# .data   0x51570..0x51678  (off = va - 0x8000)
# .bss    0x51678..0x516e4  (NOBITS)
# .plt    0x276c..0x2d38    (off==va)
GOT = 0x51350

def va_to_off(va):
    if 0x2d38 <= va < 0x402a8: return va
    if 0x402b0 <= va < 0x48a18: return va
    if 0x51570 <= va < 0x51678: return va - 0x8000
    if 0x51350 <= va < 0x51570: return va - 0x8000
    if 0x276c <= va < 0x2d38: return va
    return None

def rd(va, n):
    o = va_to_off(va)
    if o is None or o < 0 or o + n > len(data):
        return None
    return data[o:o+n]

def cstr(va, n=160):
    b = rd(va, n)
    if not b:
        return None
    s = b.split(b"\x00")[0]
    if not s:
        return None
    return s.decode("latin1", "replace")

def describe_va(v):
    """Return a short description of an absolute VA."""
    s = ""
    if 0x402b0 <= v < 0x48a18:
        st = cstr(v)
        if st is not None:
            s = f" ->rodata({st!r})"
        else:
            s = " ->rodata"
    elif 0x51570 <= v < 0x51678:
        s = " ->.data"
    elif 0x51678 <= v < 0x516e4:
        s = " ->.bss"
    elif 0x51350 <= v < 0x51570:
        s = " ->.got"
    elif 0x2d38 <= v < 0x402a8:
        s = " ->.text"
    if v in FUNCS:
        s += f" [{FUNCS[v]}]"
    return s

# ---- function names ----
FUNCS = {
    0x5188:"HI_GET_DEV_SERIAL",
    0x6000:"HI_GET_AUTHORIZATION_INFO",
    0x106a8:"HI_SDK_CREATE_URL",
    0x1f4e0:"HI_UPGRADE_CHECK_VERSION",
    0x20024:"HI_APP_UPGRADE_CHECK_VERSION",
    0x10058:"HI_INIT_PUBLICKEY",
    0x101b0:"HI_UNINIT_PUBLICKEY",
    0x101e4:"HI_SDK_FREE",
    0x103f0:"HI_SDK_CURL_SLIST_FREE",
    0x104c4:"HI_SDK_CURL_EASY_CLEANUP",
    0x10598:"HI_SDK_SET_DOMAIN",
    0x10b38:"HI_SDK_GET_DOMAIN",
    0x10b5c:"WRITE_DATA",
    0x10d0c:"HI_SDK_HTTP_POST",
    0x11344:"HI_SDK_HTTP_POST_EX",
    0x11990:"HI_SDK_HTTPS_POST_EX",
    0x12084:"HI_SDK_HTTPS_POST_BINARY",
    0x127e4:"HI_SDK_HTTPS_POST",
    0x12ddc:"HI_SDK_HTTP_GET",
    0x13304:"HI_SDK_HTTPS_GET",
    0x13e84:"HI_SDK_AES_ENCRYPTION",
    0x14044:"HI_SDK_ENCRYPT_TO_STRING",
    0x141f4:"HI_SDK_AES_DECRYPT",
    0x14520:"HI_SDK_AES_ENCRYPT",
    0x1499c:"HI_SDK_ENCRYPT_TO_HEXSTRING",
    0x14b4c:"HI_SDK_URLEncode",
    0x14fbc:"HI_SDK_HEXSTRING_TO_ENCRYPT",
    0x15344:"HI_SDK_GZCOMPRESS",
    0x15788:"HI_SDK_GZDECOMPRESS",
    0x16004:"XML_GET_TAG_CONTENT",
    0x1634c:"HI_SDK_XML_VERIFY",
    0x16e44:"HI_SDK_JSON_VERIFY_HEAP",
    0x177a0:"HI_SDK_JSON_VERIFY1",
    0x17c44:"HI_SDK_JSON_VERIFY",
    0x184c8:"HI_SDK_SIGN_CREATE",
    0x18858:"HI_SDK_SIGN_CREATE_SOUNDBAR",
    0x18adc:"HI_CREATE_RAND_STRING",
    0x199cc:"HI_GLOBAL_INIT",
    0x19fa4:"HI_GLOBAL_DEINIT",
    0x3b54:"HI_AUTH_AUTHENTICATE",
    0x3e2ac:"hi_base64_decode",
    0x3ea90:"hi_base64_encode",
    0x3f18c:"init_publickey",
    0x3f3cc:"init_privatekey",
    0x3f55c:"destroy_key",
    0x3f58c:"signsize",
    0x3f5e0:"hitvsign",
    0x3fba0:"hitvsign_soundbar",
    0x3fd3c:"hitvverify",
}

# ---- PLT (from .rel.plt order) ----
rel_plt = [
    (0x5135c,"pthread_mutex_unlock"),(0x51360,"strstr"),(0x51364,"HI_SDK_CURL_SLIST_FREE"),
    (0x51368,"fsync"),(0x5136c,"HI_SDK_HTTPS_POST"),(0x51370,"strcmp"),
    (0x51374,"__cxa_finalize"),(0x51378,"setsockopt"),(0x5137c,"curl_global_cleanup"),
    (0x51380,"curl_easy_getinfo"),(0x51384,"cJSON_GetObjectItem"),(0x51388,"printf"),
    (0x5138c,"RSA_public_encrypt"),(0x51390,"fopen"),(0x51394,"HI_SDK_CREATE_URL"),
    (0x51398,"inflate"),(0x5139c,"cJSON_Print"),(0x513a0,"fflush"),
    (0x513a4,"hitvsign"),(0x513a8,"getLogLevel"),(0x513ac,"hitvsign_soundbar"),
    (0x513b0,"curl_easy_perform"),(0x513b4,"free"),(0x513b8,"HI_SDK_JSON_VERIFY"),
    (0x513bc,"xmlFreeDoc"),(0x513c0,"pthread_mutex_lock"),(0x513c4,"ferror"),
    (0x513c8,"memcpy"),(0x513cc,"RSA_size"),(0x513d0,"curl_slist_append"),
    (0x513d4,"pthread_mutex_init"),(0x513d8,"time"),(0x513dc,"cJSON_Delete"),
    (0x513e0,"hitvverify"),(0x513e4,"ftell"),(0x513e8,"memcmp"),
    (0x513ec,"AES_set_encrypt_key"),(0x513f0,"HI_SDK_HTTP_GET"),(0x513f4,"HI_SDK_SET_DOMAIN"),
    (0x513f8,"RSA_free"),(0x513fc,"cJSON_Parse"),(0x51400,"HI_CREATE_RAND_STRING"),
    (0x51404,"deflate"),(0x51408,"HI_SDK_HTTPS_POST_BINARY"),(0x5140c,"HI_SDK_HTTPS_GET"),
    (0x51410,"xmlStrcmp"),(0x51414,"fwrite"),(0x51418,"strcat"),(0x5141c,"strcpy"),
    (0x51420,"fread"),(0x51424,"deflateInit2_"),(0x51428,"xmlNodeGetContent"),
    (0x5142c,"HI_SDK_AES_ENCRYPT"),(0x51430,"HI_SDK_AES_DECRYPT"),
    (0x51434,"xmlXPathEvalExpression"),(0x51438,"AES_cbc_encrypt"),(0x5143c,"puts"),
    (0x51440,"malloc"),(0x51444,"xmlReadFd"),(0x51448,"HI_SDK_XML_VERIFY"),
    (0x5144c,"strerror"),(0x51450,"HI_SDK_CURL_EASY_CLEANUP"),(0x51454,"HI_SDK_HTTP_POST_EX"),
    (0x51458,"HI_SDK_AES_ENCRYPTION"),(0x5145c,"__gmon_start__"),
    (0x51460,"cJSON_PrintUnformatted"),(0x51464,"xmlXPathFreeObject"),
    (0x51468,"init_publickey"),(0x5146c,"inflateEnd"),(0x51470,"strlen"),
    (0x51474,"BIO_new_mem_buf"),(0x51478,"strchr"),(0x5147c,"srand"),
    (0x51480,"PEM_read_bio_RSA_PUBKEY"),(0x51484,"fprintf"),(0x51488,"HI_SDK_URLEncode"),
    (0x5148c,"xmlXPathNewContext"),(0x51490,"RSA_public_decrypt"),
    (0x51494,"__errno_location"),(0x51498,"snprintf"),(0x5149c,"curl_global_init"),
    (0x514a0,"HI_SDK_HTTPS_POST_EX"),(0x514a4,"memset"),(0x514a8,"strncpy"),
    (0x514ac,"curl_easy_init"),(0x514b0,"AES_set_decrypt_key"),(0x514b4,"HI_SDK_GZDECOMPRESS"),
    (0x514b8,"fileno"),(0x514bc,"deflateEnd"),(0x514c0,"PEM_read_RSAPrivateKey"),
    (0x514c4,"HI_SDK_HTTP_POST"),(0x514c8,"HI_SDK_HEXSTRING_TO_ENCRYPT"),
    (0x514cc,"RSA_new"),(0x514d0,"rand"),(0x514d4,"ftruncate"),(0x514d8,"fclose"),
    (0x514dc,"MD5"),(0x514e0,"cJSON_CreateString"),(0x514e4,"HI_INIT_PUBLICKEY"),
    (0x514e8,"HI_UNINIT_PUBLICKEY"),(0x514ec,"curl_slist_free_all"),
    (0x514f0,"HI_SDK_GZCOMPRESS"),(0x514f4,"inflateInit2_"),(0x514f8,"hi_base64_encode"),
    (0x514fc,"hi_base64_decode"),(0x51500,"checkModulePermitionByID"),(0x51504,"clearerr"),
    (0x51508,"HI_SDK_ENCRYPT_TO_STRING"),(0x5150c,"sprintf"),(0x51510,"destroy_key"),
    (0x51514,"BIO_free_all"),(0x51518,"HI_SDK_SIGN_CREATE"),(0x5151c,"xmlXPathFreeContext"),
    (0x51520,"PEM_read_RSA_PUBKEY"),(0x51524,"curl_easy_setopt"),(0x51528,"cJSON_CreateObject"),
    (0x5152c,"cJSON_AddItemToObject"),(0x51530,"xmlDocGetRootElement"),
    (0x51534,"curl_easy_cleanup"),(0x51538,"fseek"),(0x5153c,"XML_GET_TAG_CONTENT"),
    (0x51540,"HI_SDK_JSON_VERIFY1"),
]
PLT_BASE = 0x2780
plt = {}
got_to_sym = {}
for i, (got, sym) in enumerate(rel_plt):
    stub = PLT_BASE + i * 12
    plt[stub] = sym
    got_to_sym[got] = sym

def resolve_branch(va):
    if va in plt:
        return "PLT->" + plt[va]
    return FUNCS.get(va)

# ---- instruction index over full .text ----
md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
md.detail = True
md.skipdata = True
text_code = data[0x2d38:0x402a8]
ALL = list(md.disasm(text_code, 0x2d38))
ADDR2IDX = {ins.address: i for i, ins in enumerate(ALL)}

def disasm_region(va, length):
    """Disassemble [va, va+length) with annotations. Returns list of lines."""
    code = rd(va, length)
    m = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN); m.detail = True
    m.skipdata = True
    local = list(m.disasm(code, va))
    lines = []
    for idx, ins in enumerate(local):
        mn = ins.mnemonic
        line = f"{ins.address:#08x}: {ins.bytes.hex():<10} {mn:<12} {ins.op_str}"
        note = None
        # branch annotation
        if mn in ("bl", "blx", "b", "b.w"):
            for op in ins.operands:
                if op.type == ARM_OP_IMM:
                    t = resolve_branch(op.imm)
                    if t:
                        note = t
        elif mn in ("beq","bne","bcs","bcc","bhi","bls","bge","blt","bgt","ble","bpl","bmi","bvs","bvc"):
            for op in ins.operands:
                if op.type == ARM_OP_IMM:
                    t = resolve_branch(op.imm)
                    if t:
                        note = "cond:" + t
        # PC-relative literal load
        if mn == "ldr":
            dst = None
            disp = None
            if ins.operands[0].type == ARM_OP_REG:
                dst = ins.operands[0].reg
            for op in ins.operands:
                if op.type == ARM_OP_MEM and op.mem.base == ARM_REG_PC:
                    disp = op.mem.disp
                    break
            if dst is not None and disp is not None:
                pool = ins.address + 8 + disp
                w = rd(pool, 4)
                if w is not None:
                    val = struct.unpack("<I", w)[0]
                    # look at next instruction for add/sub dst,pc,dst
                    nxt = local[idx + 1] if idx + 1 < len(local) else None
                    resolved = None
                    if nxt is not None and nxt.address == ins.address + 4:
                        if nxt.mnemonic in ("add", "sub") and len(nxt.operands) == 3:
                            a, b, c = nxt.operands
                            if (a.type == ARM_OP_REG and b.type == ARM_OP_REG and c.type == ARM_OP_REG
                                    and a.reg == dst and b.reg == ARM_REG_PC and c.reg == dst):
                                resolved = nxt.address + 8 + (val if nxt.mnemonic == "add" else -val)
                    if resolved is not None:
                        note = f"lit@{pool:#x} -> {resolved:#010x}{describe_va(resolved)}"
                    else:
                        note = f"lit@{pool:#x}={val:#010x}"
        # ADR: add rX, pc, #imm
        if mn == "add" and len(ins.operands) == 3:
            a, b, c = ins.operands
            if a.type == ARM_OP_REG and b.type == ARM_OP_REG and b.reg == ARM_REG_PC and c.type == ARM_OP_IMM:
                resolved = ins.address + 8 + c.imm
                note = f"ADR -> {resolved:#010x}{describe_va(resolved)}"
        # GOT access: ldr rX, [r4, #off]
        if mn == "ldr" and ins.operands[0].type == ARM_OP_REG:
            for op in ins.operands:
                if op.type == ARM_OP_MEM and op.mem.base != ARM_REG_PC and op.mem.disp >= 0 and op.mem.disp < 0x220:
                    got_addr = GOT + op.mem.disp
                    if got_addr in got_to_sym:
                        note = f"GOT[{op.mem.disp:#x}] -> {got_to_sym[got_addr]}"
                    elif op.mem.base == 4:  # r4 = GOT base
                        note = f"GOT[{op.mem.disp:#x}]"
        if note:
            line += f"   ; {note}"
        lines.append(line)
    return lines

# ---- xref sweep: find references to a target string address ----
def find_xrefs(target_va):
    out = []
    for ins in ALL:
        if ins.mnemonic == "ldr" and ins.operands[0].type == ARM_OP_REG:
            dst = ins.operands[0].reg
            for op in ins.operands:
                if op.type == ARM_OP_MEM and op.mem.base == ARM_REG_PC:
                    pool = ins.address + 8 + op.mem.disp
                    w = rd(pool, 4)
                    if w is None:
                        continue
                    val = struct.unpack("<I", w)[0]
                    idx = ADDR2IDX[ins.address]
                    if idx + 1 < len(ALL):
                        nxt = ALL[idx + 1]
                        if nxt.address == ins.address + 4 and nxt.mnemonic in ("add", "sub") and len(nxt.operands) == 3:
                            a, b, c = nxt.operands
                            if (a.type == ARM_OP_REG and b.type == ARM_OP_REG and c.type == ARM_OP_REG
                                    and a.reg == dst and b.reg == ARM_REG_PC and c.reg == dst):
                                resolved = nxt.address + 8 + (val if nxt.mnemonic == "add" else -val)
                                if resolved == target_va:
                                    out.append((ins.address, nxt.address, pool, val))
        if ins.mnemonic == "add" and len(ins.operands) == 3:
            a, b, c = ins.operands
            if a.type == ARM_OP_REG and b.type == ARM_OP_REG and b.reg == ARM_REG_PC and c.type == ARM_OP_IMM:
                resolved = ins.address + 8 + c.imm
                if resolved == target_va:
                    out.append((ins.address, ins.address, None, None))
    return out

def func_of(addr):
    best = None
    for start, name in sorted(FUNCS.items()):
        if start <= addr:
            best = (start, name)
        else:
            break
    if best:
        # check if within range (approx: use next func start)
        return best[1], best[0]
    return None, None

# =====================================================================
# MAIN
# =====================================================================
if __name__ == "__main__":
    HDR = f"# Target: {FN} (ARM32 ELF, stripped)\n"
    HDR += f"# SHA-256: {SHA}\n"
    HDR += "# Tool: capstone 5.0.6 (CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)\n"
    HDR += "# NOTE: ARM (32-bit) mode at EVEN entry VAs (NOT Thumb).\n"
    HDR += "# BL/BLX targets annotated as PLT-><import> or internal function name.\n"
    HDR += "# PC-relative literal loads (ldr rX,[pc,#imm]; add rX,pc,rX) resolved to\n"
    HDR += "#   target VA + .rodata string (pool word = PC-relative OFFSET, not absolute).\n\n"

    targets = [
        ("HI_GET_DEV_SERIAL", 0x5188, 3704, "HI_GET_DEV_SERIAL_disasm.txt"),
        ("HI_UPGRADE_CHECK_VERSION", 0x1f4e0, 2884, "HI_UPGRADE_CHECK_VERSION_disasm.txt"),
        ("HI_APP_UPGRADE_CHECK_VERSION", 0x20024, 2532, "HI_APP_UPGRADE_CHECK_VERSION_disasm.txt"),
        ("HI_SDK_CREATE_URL", 0x106a8, 1168, "HI_SDK_CREATE_URL_disasm.txt"),
        ("HI_GET_AUTHORIZATION_INFO", 0x6000, 4480, "HI_GET_AUTHORIZATION_INFO_disasm.txt"),
    ]
    for name, va, ln, fname in targets:
        lines = disasm_region(va, ln)
        txt = HDR + f"### {name} @ {va:#x} ({ln} bytes)\n\n" + "\n".join(lines) + "\n"
        open(f"{fname}", "w").write(txt)
        print("wrote", fname, len(lines), "instrs")

    # ---- XREF report ----
    xref_targets = {
        0x40bc4: "/aaa/get_dev_serial",
        0x40bc9: "substr get_dev_serial",
        0x40eec: "/aaa/get_authorizationinfo",
        0x40ef1: "substr get_authorizationinfo",
        0x40f08: "log#1 'failed to call HI_SDK_CREATE_URL_NA()' (with ESC)",
        0x40f36: "substr CREATE_URL_NA (#1)",
        0x41340: "log#2 'failed to call HI_SDK_CREATE_URL_NA()' (with ESC)",
        0x4136e: "substr CREATE_URL_NA (#2)",
        0x41324: "/aaa/sign_in_refreshtoken (context)",
        0x447e0: "http:// (scheme)",
        0x447e8: "/upgrade/check_version",
        0x447f1: "substr check_version",
        0x44844: "https:// (scheme)",
        0x449b8: "/upgrade/check_app_version",
        0x449d4: "packageName=%s&currentVersion=%s",
    }
    print("\n=== XREF SWEEP (PC-relative ldr[pc]+add / ADR over .text) ===")
    for tva, label in sorted(xref_targets.items()):
        refs = find_xrefs(tva)
        print(f"\n{label} @ {tva:#x}: {len(refs)} ref(s)")
        for (iaddr, aaddr, pool, val) in refs:
            fname, fstart = func_of(iaddr)
            pstr = (f"{pool:#x}") if pool is not None else "-"
            print(f"   ldr@{iaddr:#x} (add@{aaddr:#x}) pool={pstr} -> func {fname} (start {fstart:#x})")
