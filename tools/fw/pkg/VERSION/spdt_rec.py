import re
A="usb_EE5600FF.pkg"
lo,hi=4_890_000,4_912_000
f=open(A,'rb');f.seek(lo);b=f.read(hi-lo);f.close()
# nonzero runs
runs=[];s=None
for i,x in enumerate(b):
    if x and s is None: s=i
    if not x and s is not None:
        if i-s>=4: runs.append((lo+s,i-s))
        s=None
if s is not None: runs.append((lo+s,len(b)-s))
print("nonzero runs>=4:",len(runs))
for o,l in runs[:60]: print(o,l,b[o-lo:o-lo+min(l,48)].hex(' '))
print("--- strings >=4")
for m in re.finditer(rb'[ -~]{4,}',b):
    print(lo+m.start(),repr(m.group()[:90]))
