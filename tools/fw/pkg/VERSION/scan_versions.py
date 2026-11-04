import mmap,re,sys,hashlib,os,json
A="usb_EE5600FF.pkg"
B="usb_EE5600FF.forge-test.pkg"
pats=[("M/N/V+4dig",re.compile(rb'[MNVmnv]\d{4}')),("M0610",re.compile(rb'M0610')),("N0410",re.compile(rb'N0410')),
      ("V0100",re.compile(rb'V0100')),("version",re.compile(rb'version',re.I)),("fw_ver",re.compile(rb'fw_ver',re.I)),
      ("pkg_ver",re.compile(rb'pkg_ver',re.I)),("USB_UPG",re.compile(rb'USB_UPG')),("ver:",re.compile(rb'ver[\s_:.=]',re.I))]
u16=[("M0610_utf16", "M0610".encode('utf-16le')),("N0410_utf16","N0410".encode('utf-16le')),("V0100_utf16","V0100".encode('utf-16le'))]
out=[]
def scan(tag,path):
    with open(path,'rb') as f:
        m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
        out.append(f"== {tag} size={len(m)} sha256={hashlib.sha256(m).hexdigest()}")
        for name,p in pats:
            hits=[x.start() for x in p.finditer(m)]
            out.append(f"{name}: {len(hits)} hits {hits[:12]}")
        for name,b in u16:
            hits=[];i=m.find(b)
            while i>=0 and len(hits)<12:
                hits.append(i); i=m.find(b,i+1)
            out.append(f"{name}: {len(hits)} hits {hits[:12]}")
        m.close()
scan("A-original",A); scan("B-forge",B)
open("scan_versions.txt","w").write("\n".join(out)+"\n")
print("\n".join(out))
