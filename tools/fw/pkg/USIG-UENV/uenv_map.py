#!/usr/bin/env python3
# AP-USIG-UENV / script 2: uenv image format mapping (READ-ONLY, static)
import hashlib, math, struct, os

A = "usb_EE5600FF.pkg"
B = "usb_EE5600FF.pkg"
OUT = "USIG-UENV"
UENV = 78875832          # MtK8 offset, verified identical in A and B
DLEN = 4188
MACH = {40:"ARM", 183:"AARCH64"}

def entropy(b):
    c=[0]*256
    for x in b: c[x]+=1
    n=len(b)
    return -sum((k/n)*math.log2(k/n) for k in c if k)

def cstr(b,o):
    e=b.find(b"\0",o)
    if e<0: e=len(b)
    return b[o:e].decode("latin1")

def parse(tag, path):
    with open(path,"rb") as f:
        f.seek(UENV); img=f.read(DLEN)
    print(f"===== {tag}: bytes [{UENV},{UENV+DLEN}) len={len(img)} sha256={hashlib.sha256(img).hexdigest()}")
    print(f"first 16: {img[:16].hex(' ')}  entropy={entropy(img):.4f}")
    off=img.find(b"\x7fELF")
    print(f"ELF magic rel_offset={off} (abs {UENV+off if off>=0 else None})")
    if off<0: return img
    elf=img[off:]
    open(os.path.join(OUT,f"uenv_{tag}.elf"),"wb").write(elf)
    (ident,etype,emach,ever,entry,phoff,shoff,eflags,ehsize,phentsize,phnum,
     shentsize,shnum,shstrndx)=struct.unpack("<16sHHIIIIIHHHHHH",elf[:52])
    print(f"ELF ident={ident.hex()} class={ident[4]} data={ident[5]} osabi={ident[7]}")
    print(f"e_type={etype} e_machine={emach}({MACH.get(emach,'?')}) e_version={ever} e_entry={entry:#x}")
    print(f"e_phoff={phoff:#x} e_phnum={phnum} e_phentsize={phentsize} e_shoff={shoff:#x} e_shnum={shnum} e_shentsize={shentsize} e_shstrndx={shstrndx} e_flags={eflags:#x} e_ehsize={ehsize}")
    secs=[]
    for i in range(shnum):
        o=shoff+i*shentsize
        secs.append(struct.unpack("<IIIIIIIIII",elf[o:o+40]))
    shstr=secs[shstrndx]
    strtab=elf[shstr[4]:shstr[4]+shstr[5]]
    print("sections (idx name type flags addr off size entsize):")
    for i,sh in enumerate(secs):
        nm=cstr(strtab,sh[0]) if sh[0]<len(strtab) else "?"
        print(f"  {i:2d} {nm:<18} type={sh[1]:<2} flags={sh[2]:08x} addr={sh[3]:08x} off={sh[4]:06x} size={sh[5]:06x} ent={sh[9]}")
    for i in range(phnum):
        o=phoff+i*phentsize
        ph=struct.unpack("<8I",elf[o:o+32])
        print(f"  PH{i} type={ph[0]} off={ph[1]:#x} vaddr={ph[2]:#x} paddr={ph[3]:#x} filesz={ph[4]:#x} memsz={ph[5]:#x} flags={ph[6]:#x} align={ph[7]:#x}")
    syms=[]
    for sh in secs:
        if sh[1] in (2,11) and sh[5]:
            strsh=secs[sh[6]]
            st=elf[strsh[4]:strsh[4]+strsh[5]]
            for j in range(sh[5]//16):
                o=sh[4]+j*16
                nm,val,sz,info,other,shndx=struct.unpack("<IIIBBH",elf[o:o+16])
                if nm: syms.append((cstr(st,nm),val,sz,info,shndx))
    print(f"symbols ({len(syms)}):")
    for s in syms[:30]:
        print(f"  {s[0]:<28} val={s[1]:08x} size={s[2]:5d} info={s[3]:02x} shndx={s[4]}")
    if len(syms)>30: print(f"  ... {len(syms)-30} more")
    return img

imgs={}
for tag,path in (("A",A),("B",B)):
    imgs[tag]=parse(tag,path)

a,b=imgs["A"],imgs["B"]
diffs=[i for i in range(DLEN) if a[i]!=b[i]]
print(f"===== A-vs-B: differing bytes={len(diffs)} first={diffs[:12]} last={diffs[-12:] if diffs else []}")
if diffs:
    print(f"first_diff abs={UENV+diffs[0]} last_diff abs={UENV+diffs[-1]}")
    rs=[]; s=diffs[0]; p=diffs[0]
    for x in diffs[1:]:
        if x==p+1: p=x
        else: rs.append((s,p)); s=x; p=x
    rs.append((s,p))
    print(f"diff ranges (rel): {[(x,y,y-x+1) for x,y in rs]}")
print(f"tail 60 B (rel 4128..4188) A: {a[4128:].hex()}")
print(f"tail 60 B (rel 4128..4188) B: {b[4128:].hex()}")
kw=[b"bootargs",b"bootcmd",b"file_upgrading",b"init=",b"setenv",b"uenv",b"env",b"console",b"root=",b"mtdparts",b"/bin/sh",b"cmdline",b"bootdelay",b"baudrate"]
for k in kw:
    pa=[i for i in range(DLEN) if a.startswith(k,i)]
    pb=[i for i in range(DLEN) if b.startswith(k,i)]
    print(f"keyword {k!r}: A={pa} B={pb}")
