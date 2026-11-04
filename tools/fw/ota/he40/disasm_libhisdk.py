#!/usr/bin/env python3
# Static disassembly of OTA sign functions in libhisdk.so (ARM 32-bit).
# Evidence: prologue bytes are ARM (e.g. 0x3f3cc = e92d4810 'push {r4,r11,lr}'),
# NOT Thumb. Capstone 5.0.6, read-only.
import struct
from capstone import *
from capstone.arm import *

FN = "libhisdk.so"
data = open(FN, "rb").read()

def va_to_off(va):
    if 0x2d38 <= va < 0x402a8:   # .text
        return va
    if 0x402b0 <= va < 0x48a18:  # .rodata
        return va
    if 0x51570 <= va < 0x51678:  # .data
        return va - 0x8000
    if 0x51350 <= va < 0x51570:  # .got
        return va - 0x8000
    if 0x276c <= va < 0x2d38:    # .plt
        return va
    return None

def rd(va, n):
    o = va_to_off(va)
    if o is None or o < 0 or o + n > len(data):
        return None
    return data[o:o+n]

funcs = {
    0x3f5e0:"hitvsign", 0x3fba0:"hitvsign_soundbar", 0x3fd3c:"hitvverify",
    0x3f18c:"init_publickey", 0x3f3cc:"init_privatekey", 0x3f55c:"destroy_key",
    0x3f58c:"signsize", 0x184c8:"HI_SDK_SIGN_CREATE", 0x3b54:"HI_AUTH_AUTHENTICATE",
    0x6000:"HI_GET_AUTHORIZATION_INFO", 0x10058:"HI_INIT_PUBLICKEY",
    0x101b0:"HI_UNINIT_PUBLICKEY", 0x18858:"HI_SDK_SIGN_CREATE_SOUNDBAR",
    0x3ea90:"hi_base64_encode", 0x3e2ac:"hi_base64_decode",
    0x14520:"HI_SDK_AES_ENCRYPT", 0x141f4:"HI_SDK_AES_DECRYPT", 0x13e84:"HI_SDK_AES_ENCRYPTION",
    0x14044:"HI_SDK_ENCRYPT_TO_STRING", 0x1499c:"HI_SDK_ENCRYPT_TO_HEXSTRING",
    0x14fbc:"HI_SDK_HEXSTRING_TO_ENCRYPT", 0x14b4c:"HI_SDK_URLEncode",
    0x18adc:"HI_CREATE_RAND_STRING", 0x12084:"HI_SDK_HTTPS_POST_BINARY",
    0x127e4:"HI_SDK_HTTPS_POST", 0x13304:"HI_SDK_HTTPS_GET", 0x12ddc:"HI_SDK_HTTP_GET",
    0x10d0c:"HI_SDK_HTTP_POST", 0x11344:"HI_SDK_HTTP_POST_EX", 0x11990:"HI_SDK_HTTPS_POST_EX",
    0x10598:"HI_SDK_SET_DOMAIN", 0x106a8:"HI_SDK_CREATE_URL", 0x104c4:"HI_SDK_CURL_EASY_CLEANUP",
    0x103f0:"HI_SDK_CURL_SLIST_FREE", 0x102b8:"HI_SDK_JUDGE_XML_FORM",
    0x1634c:"HI_SDK_XML_VERIFY", 0x15344:"HI_SDK_GZCOMPRESS", 0x15788:"HI_SDK_GZDECOMPRESS",
    0x177a0:"HI_SDK_JSON_VERIFY1", 0x17c44:"HI_SDK_JSON_VERIFY", 0x16e44:"HI_SDK_JSON_VERIFY_HEAP",
    0x199cc:"HI_GLOBAL_INIT", 0x19fa4:"HI_GLOBAL_DEINIT",
    0x16004:"XML_GET_TAG_CONTENT", 0x10b5c:"WRITE_DATA",
    0x10b38:"HI_SDK_GET_DOMAIN", 0x101e4:"HI_SDK_FREE",
}

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

plt_base = 0x2780  # first real PLT entry (PLT0 resolver occupies 0x276c..0x2780)
plt = {}
for i, (got, sym) in enumerate(rel_plt):
    stub = plt_base + i*12
    plt[stub] = (got, sym)

def resolve_target(va):
    if va in plt:
        return "PLT->"+plt[va][1]
    f = funcs.get(va)
    if f:
        return f
    return None

def describe_ptr(v):
    """Describe a pointer value v (absolute)."""
    s = ""
    if 0x402b0 <= v < 0x48a18:
        raw = rd(v, 64)
        if raw:
            printable = bytes(b if 32 <= b < 127 else 46 for b in raw).decode()
            s = f" ->rodata({printable!r})"
    elif 0x51570 <= v < 0x51678:
        s = " ->.data"
    elif 0x51678 <= v < 0x516e4:
        s = " ->.bss"
    elif 0x51350 <= v < 0x51570:
        s = " ->.got"
    if v in funcs:
        s += f" [{funcs[v]}]"
    return s

def disasm(name, va, length, out):
    code = rd(va, length)
    if code is None:
        out.append(f"!! cannot read {length} bytes at {va:#x}\n")
        return
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    lines = []
    for insn in md.disasm(code, va):
        mnem = insn.mnemonic
        ops = insn.op_str
        line = f"{insn.address:#08x}: {insn.bytes.hex():<10} {mnem:<12} {ops}"
        note = None
        if mnem in ("bl","blx","b","b.w"):
            for op in insn.operands:
                if op.type == ARM_OP_IMM:
                    t = resolve_target(op.imm)
                    if t:
                        note = t
        elif mnem in ("beq","bne","bcs","bcc","bhi","bls","bge","blt","bgt","ble","bpl","bmi","bvs","bvc"):
            for op in insn.operands:
                if op.type == ARM_OP_IMM:
                    t = resolve_target(op.imm)
                    if t:
                        note = "cond:"+t
        if mnem in ("ldr","ldr.w","adr","adr.w"):
            for op in insn.operands:
                if op.type == ARM_OP_MEM and op.mem.base == ARM_REG_PC:
                    addr = insn.address + 8 + op.mem.disp
                    val = rd(addr, 4)
                    if val is not None:
                        v = struct.unpack("<I", val)[0]
                        note = f"lit@{addr:#x}={v:#010x}{describe_ptr(v)}"
                elif op.type == ARM_OP_IMM and mnem.startswith("adr"):
                    note = f"ADR->{op.imm:#010x}"
        if note:
            line += f"   ; {note}"
        lines.append(line)
    out.append(f"### {name} @ {va:#x} ({length} bytes)\n")
    out.append("\n".join(lines))
    out.append("")

out = []
targets = [
    ("init_privatekey", 0x3f3cc, 400),
    ("init_publickey", 0x3f18c, 576),
    ("hitvsign", 0x3f5e0, 1472),
    ("hitvverify", 0x3fd3c, 1248),
    ("HI_SDK_SIGN_CREATE", 0x184c8, 912),
    ("HI_AUTH_AUTHENTICATE", 0x3b54, 5684),
    ("HI_GET_AUTHORIZATION_INFO", 0x6000, 4480),
    ("destroy_key", 0x3f55c, 48),
]
for nm, va, ln in targets:
    disasm(nm, va, ln, out)

# helper functions referenced by init_privatekey/init_publickey
out.append("=== EXTRA HELPERS ===\n")
for nm, va, ln in [("helper_0x2bd0", 0x2bd0, 120), ("helper_0x3efb4", 0x3efb4, 470), ("helper_0x28e8", 0x28e8, 80), ("helper_0x2abc(strlen?)", 0x2abc, 12), ("helper_0x2aec(PEM_read_bio_RSA_PUBKEY?)", 0x2aec, 12)]:
    disasm(nm, va, ln, out)

out.append("### gpKey pointer analysis")
g = rd(0x51550, 4)
out.append(f"GOT[0x51550] (R_ARM_GLOB_DAT gpKey) = {struct.unpack('<I',g)[0]:#010x}  (load-time: &gpKey=0x516b0)")
out.append(f".data section bytes @0x51570:")
dd = rd(0x51570, 0x108)
for i in range(0, len(dd), 16):
    out.append(f"  0x{0x51570+i:08x}: {dd[i:i+16].hex()}")
out.append("")

txt = "\n".join(out)
open("_all_disasm.txt","w").write(txt)
print(txt)
