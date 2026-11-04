import sys, subprocess, re
# add capstone to sys.path yourself if needed
from capstone import *
data = open('libota.so','rb').read()
md = Cs(CS_ARCH_ARM, CS_MODE_ARM+CS_MODE_LITTLE_ENDIAN)
md.detail = True
# otaCheckVersion @ 0xf41c (2088 B) -> 0xfc44 ; his_ota_check_version @ 0xe62c (1440)
out=[]
# find .text bounds
for line in subprocess.check_output(['readelf','-SW','libota.so']).decode().splitlines():
    if ' .text ' in line:
        p=line.split(); addr=int(p[3],16); off=int(p[4],16); size=int(p[5],16)
        for fn_va, fn_name in [(0xf41c,'otaCheckVersion'), (0xe62c,'his_ota_check_version')]:
            foff = off + (fn_va - addr)
            code = md.disasm(data[foff:foff+2500], fn_va)
            n=0
            for i in code:
                out.append(f"0x{i.address:08x}: {i.bytes.hex():8s} {i.mnemonic:7s} {i.op_str}")
                n+=1
                if n>520: break
        break
open('libota_checkversion_disasm.txt','w').write("\n".join(out))
print("wrote", len(out))
