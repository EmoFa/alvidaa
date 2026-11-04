import struct, sys
# add capstone to sys.path yourself if needed
from capstone import *
from capstone.arm import *
data = open('libtvsysinfo.so','rb').read()
# find "HI_GET_DEV_SERIAL" PLT target: find import name -> GOT; simpler: scan for the string then xref by scanning for bl to PLT stub
# Get PLT stub addr for HI_GET_DEV_SERIAL via .rel.plt
# Use readelf-like: just scan text for 'bl' to the PLT entry
# Simpler: disassemble whole .text, find calls to HI_GET_DEV_SERIAL via imported name resolution is complex.
# Instead: find string refs and dump function containing them.
md = Cs(CS_ARCH_ARM, CS_MODE_ARM+CS_MODE_LITTLE_ENDIAN)
md.detail = True
# Find imported symbol address from dynsym: HI_GET_DEV_SERIAL
# Use ELF parsing minimal: find .dynsym entries
import subprocess
out = subprocess.check_output(['readelf','-sW','--dyn-syms','libtvsysinfo.so']).decode()
# find HI_GET_DEV_SERIAL
for line in out.splitlines():
    if 'HI_GET_DEV_SERIAL' in line and 'UND' in line:
        print("UND:", line.strip())
    if 'HI_GET_DEV_SERIAL' in line and 'UND' not in line:
        print("DEF:", line.strip())
# find reloc for HI_GET_DEV_SERIAL
out2 = subprocess.check_output(['readelf','-rW','libtvsysinfo.so']).decode()
for line in out2.splitlines():
    if 'HI_GET_DEV_SERIAL' in line:
        print("RELOC:", line.strip())
