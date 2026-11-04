import hashlib,zlib
A="usb_EE5600FF.pkg"
stored=bytes.fromhex("6bf0504aef8c2116c787a13e8ebaa2f4d7fd719c1b7ab9facf0418887e7e8957")
f=open(A,'rb')
def R(o,n): f.seek(o); return f.read(n)
L=0x02800040
cands=[(512,L),(512,L-63),(575,L-63),(575,L-64),(451,L),(451,L+61),(0x1FF,L)]
algs={'md5':hashlib.md5,'sha1':hashlib.sha1,'sha256':hashlib.sha256,'sha512':hashlib.sha512,'blake2s':hashlib.blake2s,'sha3_256':hashlib.sha3_256,'sm3':None}
res=[]
for o,n in cands:
    d=R(o,n)
    for name,fn in algs.items():
        if fn is None:
            try: h=hashlib.new('sm3',d).digest()
            except Exception: continue
        else: h=fn(d).digest()
        hit=(h[:32]==stored) or (h[-32:]==stored)
        res.append((o,n,name,h.hex()[:16],hit))
    c=zlib.crc32(d)
    res.append((o,n,'crc32',f"{c:08x}",c==int.from_bytes(stored[:4],'big')))
print("stored",stored.hex())
for r in res: print(r)
print("any MATCH",any(r[4] for r in res))
print("offsets hex: ver",hex(4903487),"rel",hex(4903487-512),"desc",hex(0x1C3),"hash",hex(0x1DF),"spdt_end",hex(41943616))
