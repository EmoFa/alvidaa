import hashlib,os
A="usb_EE5600FF.pkg"
B="usb_EE5600FF.pkg"
F="usb_EE5600FF.forge-test.pkg"
C="usb_EE5600FF.N0410-test.pkg"
def R(p,o,n):
    with open(p,'rb') as f: f.seek(o); return f.read(n)
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1<<20),b''): h.update(c)
    return h.hexdigest()
L=[];w=L.append
w("AP-61-PKGVER / diff_version.txt (Offsets absolut, 0-basiert; Originale read-only)")
w("")
w("== 1. A (M0610) ./. F (AQDA-Forge-Test)")
fa=open(A,'rb');ff=open(F,'rb');total=0;first=None;last=None;blocks=0
for off in range(0,613234831,1<<20):
    n=min(1<<20,613234831-off);a=fa.read(n);f=ff.read(n)
    if a!=f:
        blocks+=1
        for i,(x,y) in enumerate(zip(a,f)):
            if x!=y:
                total+=1
                if first is None: first=off+i
                last=off+i
w("Differenzbytes gesamt: %d in %d 1-MiB-Bloecken"%(total,blocks))
w("erste Diff-Position: %d (0x%x)  letzte: %d (0x%x)"%(first,first,last,last))
w("erwartete Struktur: flags-Byte @80991127 (0x101->0x100) + 3rdw-Datenfenster [80991183,420096319)")
w("Version @4903487 A: %s | F: %s | gleich=%s"%(R(A,4903487,5).hex(' '),R(F,4903487,5).hex(' '),R(A,4903487,5)==R(F,4903487,5)))
w("spdt-Hash @479 gleich=%s"% (R(A,479,32)==R(F,479,32)))
w("Header 0x00-0x8F gleich=%s ; usig+Trailer [613234319,613234831) gleich=%s"%(
    R(A,0,0x90)==R(F,0,0x90), R(A,613234319,512)==R(F,613234319,512)))
w("=> Forge-Test traegt unveraendert M0610; eine Versionsaenderung muesste zusaetzlich zu F erfolgen.")
w("")
w("== 2. A (M0610) ./. B (E011_M0111), Kontrollbuild")
w("Groessen: A %d, B %d"%(os.path.getsize(A),os.path.getsize(B)))
w("Version @4903487 A: %s | B: %s"%(R(A,4903487,5).hex(' '),R(B,4903487,5).hex(' ')))
w("spdt-Hash @479 A: %s | B: %s"%(R(A,479,32).hex(),R(B,479,32).hex()))
w("=> gleiche Position, anderer 4-Zeichen-Wert, anderer spdt-Hash (Korrelation, kein Algorithmusbeweis).")
w("")
w("== 3. A ./. C (statische N0410-Kopie, NICHT deployt)")
w("Datei: %s"%C)
w("Groesse: %d  sha256: %s"%(os.path.getsize(C),sha(C)))
w("Aenderung: 'M0610' -> 'N0410' @4903487")
w("  4903487: 4d -> 4e  (M -> N)")
w("  4903489: 36 -> 34  (6 -> 4)")
w("  4903488/4903490/4903491 bleiben 30/31/30 ('0','1','0')")
# verify diffs
a=open(A,'rb');c=open(C,'rb');d=[]
for off in range(0,613234831,1<<20):
    n=min(1<<20,613234831-off);x=a.read(n);y=c.read(n)
    if x!=y:
        d += [off+i for i,(p,q) in enumerate(zip(x,y)) if p!=q]
w("verifizierte Diff-Positionen A vs C: %s (Anzahl %d)"%(d,len(d)))
w("spdt-Hash @479 in C unveraendert: %s"%R(C,479,32).hex())
w("=> Wenn der spdt-Hash deterministisch ueber das Fenster [511/512, +41943104) laeuft, ist der gespeicherte Wert jetzt falsch.")
w("=> Ohne bekannten Algorithmus/Schluessel ist der korrekte Ersatzwert nicht berechenbar.")
w("")
w("== 4. Was NICHT bricht")
w("aqda-Hash @80956071: Version liegt ausserhalb [80956103,80991123) -> unberuehrt.")
w("usig 256B @613234319 und Trailer @613234575: unberuehrt, aber Signatur-Semantik unbekannt.")
w("3rdw-Subhash @80991151 und 3rdw-data: unberuehrt.")
w("80B-Block 0x40-0x8F: unberuehrt (Kandidat dateiweite Integritaet, Algorithmus unbekannt).")
open("diff_version.txt","w").write("\n".join(L)+"\n")
print("\n".join(L))
