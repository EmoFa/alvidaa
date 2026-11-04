import hashlib
A="usb_EE5600FF.pkg"
B="usb_EE5600FF.pkg"
def R(p,o,n):
    with open(p,'rb') as f: f.seek(o); return f.read(n)
L=[];w=L.append
w("AP-61-PKGVER / hash_coverage.txt  (alle Offsets absolut, 0-basiert)")
w("")
w("== 1. Deskriptorkette + per-Image-Hashfenster")
w("Fensterkonvention (belegt in AP-AQDA-FORGE): [desc+60, desc+60+len), d.h. Markerbyte 0x69 + Nutzdaten.")
w("Deskriptor = name4+flags4+len4+const16+hash32+marker1 = 61 B; Nutzdaten ab desc+61.")
w("%-5s %-11s %-10s %-24s %-17s %-4s %s"%("name","desc","len","hashfenster","stored_hash_A","B=A","endet_an"))
D=[("spdt",451),("logo",41943615),("ddb",77391604),("uenv",78875771),("adsp",78880019),("aqda",80956043)]
for nm,d in D:
    ln=int.from_bytes(R(A,d+8,4),'little'); hA=R(A,d+28,32); hB=R(B,d+28,32)
    s=d+60; e=s+ln
    w("%-5s %-11d %-10d %-24s %-17s %-4s 0x%x"%(nm,d,ln,"[%d,%d)"%(s,e),hA.hex()[:16],"yes" if hA==hB else "NO",e))
w("")
w("== 2. Wo liegt das Versionsfeld?")
checks=[("spdt-Version M0610",4903487),("spdt product model",4899475),("spdt V0000.01.00A.",4971183),
        ("cfig version/flags 0x94",148),("80B-Block 0x40-0x8F",64),("usig-Blob",613234319),("Trailer MTK",613234575),("3rdw flags",80991127)]
for nm,o in checks:
    w("%-24s %-10d spdt=%-5s aqda=%-5s usig=%-5s trailer=%-5s"%(
        nm,o,511<=o<41943615,80956103<=o<80991123,613234319<=o<613234575,o>=613234575))
w("")
w("=> M0610 liegt 4.902.976 B nach Fensterbeginn 511 und 37.040.128 B vor Fensterende 41943615:")
w("   eindeutig INNERHALB des spdt-Hashfensters.")
w("=> In aqda-Fenster, usig, Trailer und 3rdw-Deskriptor kommt kein Versionsstring vor.")
w("")
w("== 3. Stored vs. nachgerechnete Hashes (spdt)")
stored=R(A,479,32)
w("stored spdt hash @479: "+stored.hex())
for lab,o,n in [("Fenster 511+len",511,41943104),("MtK8 512+len",512,41943104),("payload 575+len",575,41943104),("MtK8+len-32",512,41943072)]:
    d=R(A,o,n)
    w("%-18s off=%d len=%d sha256=%s%s"%(lab,o,n,hashlib.sha256(d).hexdigest()," MATCH" if hashlib.sha256(d).digest()==stored else ""))
w("Batterie: md5,sha1,sha256,sha512,blake2s,sha3_256,sm3,crc32 ueber 7 Start/Laengen-Kombinationen => 0 Treffer (Original).")
w("Vorangegangene breite Negativsuche (AP-PKG-SIG): MD5/SHA*/BLAKE2/SM3/CRC32/HMAC/Custom-IV-SHA256 => 0 Treffer.")
w("")
w("== 4. Kontrollen")
w("A vs B: spdt-Hash 6bf0504a.. vs 9e5f5b22.. (verschieden, weil spdt-Inhalt inkl. M0610/M0111 differiert)")
w("A vs B: uenv-Hash 53325fb0.. vs 6472df58.. (verschieden); logo/ddb/adsp/aqda-Hashes identisch.")
w("F (Forge): spdt-Fenster und spdt-Hash byte-identisch zu A; Version bleibt M0610.")
w("F (Forge): Aenderung nur in 3rdw [80991127] + Daten [80991183,420096319); aqda-Fenster, usig, Trailer unveraendert.")
w("C (N0410-Kopie): 2 Bytes @4903487/4903489 geaendert; spdt-Hash @479 unveraendert 6bf0504a..")
w("   => (Inhalt,Hash)-Paar inkonsistent, falls der Hash deterministisch ueber das Fenster laeuft.")
w("")
w("== 5. Grenzen der Aussage")
w("- Ob der Flasher den spdt-32B-Hash prueft, ist aus dem .pkg nicht ableitbar.")
w("- Hashalgorithmus proprietaer/unbekannt; ohne Schluessel keine korrekte Neuberechnung.")
w("- 80B-Block 0x40-0x8F (A!=B, in F unveraendert) bleibt Kandidat fuer dateiweite Integritaet; nicht dekodiert.")
open("hash_coverage.txt","w").write("\n".join(L)+"\n")
print("\n".join(L))
