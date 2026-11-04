import mmap, struct, os, sys

A = "usb_EE5600FF.pkg"
MTK8 = 80956104  # aqda MtK8 offset
COV = 35020      # descriptor length (covered region [MTK8, MTK8+COV))

with open(A, "rb") as f:
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

fsize = len(mm)
print(f"file size = {fsize}")

trailer = fsize - 256
span = trailer - MTK8
print(f"aqda MtK8 = {MTK8} (0x{MTK8:x}), trailer = {trailer}, span = {span}")
print(f"covered region = [{MTK8}, {MTK8+COV})  (len {COV})")

# find all 0xEF53 occurrences (ext4 superblock magic @ superblock+0x38)
magic = b'\x53\xef'
positions = []
i = 0
reg = mm[MTK8:trailer]
while True:
    j = reg.find(magic, i)
    if j < 0: break
    positions.append(j)
    i = j + 1
print(f"\nTotal 0xEF53 occurrences in aqda span: {len(positions)}")
print("First 60 positions (rel to MtK8, and abs):")
for j in positions[:60]:
    print(f"  rel {j:>9}  abs {MTK8+j}")

# Also find gzip and bzip2 signatures
print("\ngzip 0x1f8b occurrences (first 20):")
i = 0; n = 0
while True:
    j = reg.find(b'\x1f\x8b\x08', i)
    if j < 0: break
    print(f"  rel {j:>9}  abs {MTK8+j}")
    n += 1
    if n >= 20: break
    i = j + 1

print("\nbzip2 'BZh' occurrences (first 20):")
i = 0; n = 0
while True:
    j = reg.find(b'BZh', i)
    if j < 0: break
    print(f"  rel {j:>9}  abs {MTK8+j}")
    n += 1
    if n >= 20: break
    i = j + 1
