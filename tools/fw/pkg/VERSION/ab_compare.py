import re,hashlib
A="usb_EE5600FF.pkg"
B="usb_EE5600FF.pkg"
import os
for p in (A,B): print(os.path.basename(os.path.dirname(p)),os.path.getsize(p),hashlib.sha256(open(p,'rb').read()).hexdigest())
fa=open(A,'rb');fb=open(B,'rb')
def R(f,o,n): f.seek(o); return f.read(n)
print("spdt desc hash A",R(fa,0x1DF,32).hex())
print("spdt desc hash B",R(fb,0x1DF,32).hex())
print("A spdt hdr",R(fa,0x1DF-60,64).hex())
print("B spdt hdr",R(fb,0x1DF-60,64).hex())
# version-like strings in B
mb=open(B,'rb').read() if False else None
import mmap
m=mmap.mmap(fb.fileno(),0,access=mmap.ACCESS_READ)
for nm,pat in [("MNV4",rb'[MNV]\d{4}'),("M0610",rb'M0610'),("M0111",rb'M0111'),("N0410",rb'N0410'),("V0000",rb'V0000')]:
    hits=[x.start() for x in re.finditer(pat,m)]
    print("B",nm,len(hits),hits[:10], [m[h:h+8] for h in hits[:3]])
# diff spdt windows
a=R(fa,512,41943104); b=R(fb,512,41943104)
diffs=[i for i in range(len(a)) if a[i]!=b[i]]
print("spdt diff bytes",len(diffs),"first",diffs[:20],"last",diffs[-10:] if diffs else [])
# group into ranges
rg=[]
if diffs:
    s=p=diffs[0]
    for i in diffs[1:]:
        if i==p+1: p=i
        else: rg.append((512+s,512+p-s+1)); s=p=i
    rg.append((512+s,512+p-s+1))
print("spdt diff ranges",len(rg)); print(rg[:20])
for o,l in rg[:6]:
    print(o,l,R(fa,o,min(l,32)).hex(' '),"|",R(fb,o,min(l,32)).hex(' '))
