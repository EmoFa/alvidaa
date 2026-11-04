A="usb_EE5600FF.pkg"
S,E=512,41943616
with open(A,'rb') as f: f.seek(S); d=f.read(E-S)
nz=[i for i,b in enumerate(d) if b]
print("spdt len",len(d),"nonzero",len(nz),"first",nz[0],"last",nz[-1])
# 64KB blocks with nonzero
blocks=[]
for o in range(0,len(d),65536):
    c=sum(1 for b in d[o:o+65536] if b)
    if c: blocks.append((S+o,c))
print("64K nonzero blocks:",len(blocks))
print(blocks[:40])
# strings >=8 in [4.8M,5.7M) abs
import re
lo,hi=4_800_000,5_700_000
f=open(A,'rb');f.seek(lo);buf=f.read(hi-lo);f.close()
for m in re.finditer(rb'[ -~]{8,}',buf):
    print(lo+m.start(), repr(m.group()[:100]))
