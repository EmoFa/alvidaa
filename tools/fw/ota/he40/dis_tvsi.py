import sys
# add capstone to sys.path yourself if needed
from capstone import *
from capstone.arm import *
data = open('libtvsysinfo.so','rb').read()
md = Cs(CS_ARCH_ARM, CS_MODE_ARM+CS_MODE_LITTLE_ENDIAN)
md.detail = True
# .text section bounds via readelf
import subprocess,re
out = subprocess.check_output(['readelf','-SW','libtvsysinfo.so']).decode()
for line in out.splitlines():
    if ' .text ' in line:
        m = re.search(r'\[ (\w+)\]', line)
        parts = line.split()
        # find addr and offset
        print("TEXT:", line.strip())
        addr = int(parts[3],16); off = int(parts[4],16); size = int(parts[5],16)
        text = data[off:off+size]
        code = md.disasm(text, addr)
        outl=[]
        for i in code:
            ops = i.op_str
            outl.append(f"0x{i.address:08x}: {i.bytes.hex():8s} {i.mnemonic:8s} {ops}")
        open('libtvsysinfo_disasm.txt','w').write("\n".join(outl))
        print("wrote", len(outl), "instr")
