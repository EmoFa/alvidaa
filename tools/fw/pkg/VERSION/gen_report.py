import hashlib,os,zlib
A="usb_EE5600FF.pkg"
B="usb_EE5600FF.pkg"
F="usb_EE5600FF.forge-test.pkg"
C="usb_EE5600FF.N0410-test.pkg"
def R(p,o,n):
    with open(p,'rb') as f: f.seek(o); return f.read(n)
def hx(b): return b.hex(' ')
def asc(b): return ''.join(chr(c) if 32<=c<127 else '.' for c in b)
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1<<20),b''): h.update(c)
    return h.hexdigest()
sz=lambda p: os.path.getsize(p)
L=[]
L.append("AP-61-PKGVER / version_map.txt")
L.append("A original  %s  %d B  sha256 %s"%(A,sz(A),sha(A)))
L.append("B M0111     %s  %d B  sha256 %s"%(B,sz(B),sha(B)))
L.append("F forge     %s  %d B  sha256 %s"%(F,sz(F),sha(F)))
L.append("C N0410copy %s  %d B  sha256 %s"%(C,sz(C),sha(C)))
L.append("")
L.append("== 1. alle Versionskandidaten (ASCII, 0-basiert)")
L.append("Feld                     abs_off    hex        A bytes          B bytes          F bytes          Kontext")
rows=[
 ("M0610/M0111 data_version",4903487,"0x4ad23f","4d 30 36 31 30 00","4d 30 31 31 31 00","4d 30 36 31 30 00",".data_version/.serial_product_list TLV-Bereich der spdt; einziger M####-Treffer"),
 ("product model",4899475,"0x4ac293","48 45 34 30 45 35 36 30 30 46 46 57 54 53","same","same",".serial_product_list-Wert HE40E5600FFWTS"),
 ("V0000.01.00A.",4971183,"0x4bdaaf","56 30 30 30 30 2e 30 31 2e 30 30 41 2e","same","same","10x im 64KiB-Raster, build-invariant; kein M/N-Diskriminator"),
 ("cfig version/flags",148,"0x94","00 00 00 00","same","same","Headerfeld 'Version/Flags', in A und B Null"),
]
for r in rows: L.append("%-24s %-10d %-10s %-16s %-16s %-16s %s"%r)
L.append("")
L.append("V0000.01.00A. Positionen: "+", ".join(str(4971183+65536*k) for k in range(10)))
L.append("USB_UPG_VERSION Label (kein Wert): 523, 41943687, 77391676, 78875843, 78880091, 80956115")
L.append("")
L.append("== 2. Hexdump um 0x4AD23F")
for tag,p in (("A",A),("B",B),("F",F),("C",C)):
    o=4903487
    s=o-16; d=R(p,s,48)
    L.append(tag+" @"+hex(s)+"  "+hx(d)+"  |"+asc(d)+"|")
L.append("")
L.append("== 3. TLV-Nachbarschaft (A)")
for o,l in [(4899409,16),(4899421,32),(4899445,44),(4899473,20),(4903487,6)]:
    d=R(A,o,l); L.append(str(o)+" "+hex(o)+" "+hx(d)+" |"+asc(d)+"|")
L.append("")
L.append("== 4. Negativsuche (roher Byte-Scan, beide Pakete)")
L.append("M0610: A 1 Treffer (4903487), B 0, F 1 (4903487)")
L.append("N0410: A 0, B 0, F 0, C 1 (4903487, kuenstlich)")
L.append("V0100: A 0, B 0; UTF-16LE/UTF-16BE M0610/N0410/V0100: 0")
L.append("USB_UPG_VERSION: 6 Treffer = nur MtK8-Label, keine Version")
L.append("Nicht erfasst: komprimierte/transformierte Bereiche (aqda-Nutzdaten) im Rohscan.")
open("version_map.txt","w").write("\n".join(L)+"\n")
print("\n".join(L))
