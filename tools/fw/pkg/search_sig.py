#!/usr/bin/env python3
"""Search for RSA/ECDSA/ASN.1 signature structures (READ-ONLY)."""
import mmap, re

A = "usb_EE5600FF.pkg"
B = "usb_EE5600FF.pkg"

RSA_OID = bytes.fromhex('2a864886f70d010101')  # 1.2.840.113549.1.1.1 (rsaEncryption)
RSA_OID_ALT = bytes.fromhex('06092a864886f70d010101')
EC_OID = bytes.fromhex('2a8648ce3d')            # 1.2.840.10045

def scan(path, tag):
    f=open(path,'rb'); m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
    size = len(m)
    print(f"\n===== {tag} (size={size}) =====")
    # regions of interest: header, each descriptor, trailer
    MTK8=[512,41943676,77391665,78875832,78880080,80956104]
    regions = {}
    regions['header_0_0x200'] = (0, 0x200)
    regions['trailer'] = (size-256, size)
    for i,o in enumerate(MTK8):
        name_off = 0x1C3 if o==512 else o-61
        regions[f'desc{i}_{name_off}'] = (name_off, o)
        regions[f'mtk8hdr{i}'] = (o, o+64)

    for rname,(s,e) in regions.items():
        data = m[s:e]
        for name, oid in [('RSA_OID',RSA_OID), ('RSA_OID_ASN1',RSA_OID_ALT), ('EC_OID',EC_OID)]:
            i = data.find(oid)
            if i>=0:
                print(f"  {rname}: {name} FOUND at +0x{i:X} (abs 0x{s+i:X})")
        # DER SEQUENCE 30 82 xx xx
        for mm_ in re.finditer(b'\x30\x82', data):
            i = mm_.start()
            print(f"  {rname}: DER SEQ 0x30 0x82 at +0x{i:X} (abs 0x{s+i:X}): {data[i:i+8].hex()}")
        for mm_ in re.finditer(b'\x30\x81', data):
            i = mm_.start()
            print(f"  {rname}: DER SEQ 0x30 0x81 at +0x{i:X}: {data[i:i+8].hex()}")
    f.close(); m.close()

scan(A, 'A')
scan(B, 'B')

# Also check the 64B and 80B blocks for RSA modulus-like properties
print("\n=== 64B block RSA-modulus checks ===")
f=open(A,'rb'); m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
b64 = m[0:0x40]
b80 = m[0x40:0x90]
print("64B block:", b64.hex())
print("  first byte 0x%02X (top bit set=%s), last byte 0x%02X (odd=%s)" % (
    b64[0], bool(b64[0]&0x80), b64[-1], bool(b64[-1]&1)))
print("80B block:", b80.hex())
print("80B[0:64]:", b80[0:64].hex())
print("80B[64:80]:", b80[64:80].hex())
import struct
n = int.from_bytes(b64, 'big')
s = int.from_bytes(b80[0:64], 'big')
print("64B as bigint bits:", n.bit_length())
print("80B[0:64] as bigint bits:", s.bit_length())
print("sig < modulus?", s < n)
f.close(); m.close()
