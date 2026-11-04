import mmap, struct

A = "usb_EE5600FF.pkg"
MTK8 = 80956104
COV = 35020

with open(A, "rb") as f:
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

fsize = len(mm)
trailer = fsize - 256
reg = mm[MTK8:trailer]

def u32(b, off):
    return struct.unpack_from("<I", b, off)[0]

# Scan for real ext4 superblocks: magic 0xEF53 at superblock offset 0x38,
# superblock located at fs_start + 1024.
magic = b'\x53\xef'
positions = []
i = 0
while True:
    j = reg.find(magic, i)
    if j < 0: break
    positions.append(j)
    i = j + 1

# For each candidate, parse superblock. Dedup by filesystem start.
found = {}
for j in positions:
    fs_start = j - 1080  # magic at fs+1024+56
    if fs_start < 0:
        continue
    sb_off = fs_start + 1024
    if sb_off + 1024 > len(reg):
        continue
    # verify magic again at sb+0x38
    if reg[sb_off+0x38:sb_off+0x3a] != b'\x53\xef':
        continue
    log_bs = u32(reg, sb_off+0x18)
    if log_bs > 6:
        continue
    blocks_lo = u32(reg, sb_off+0x04)
    block_size = 1024 << log_bs
    if blocks_lo == 0 or block_size * blocks_lo > len(reg):
        continue
    if fs_start in found:
        continue
    rev = u32(reg, sb_off+0x4C)
    inodes = u32(reg, sb_off+0x00)
    bpg = u32(reg, sb_off+0x20)
    ipg = u32(reg, sb_off+0x28)
    fdb = u32(reg, sb_off+0x14)
    vol = reg[sb_off+0x78:sb_off+0x88]
    vol = vol.split(b'\x00')[0].decode('latin1', 'replace')
    state = struct.unpack_from("<H", reg, sb_off+0x3A)[0]
    total = block_size * blocks_lo
    found[fs_start] = dict(fs_start=fs_start, log_bs=log_bs, block_size=block_size,
                           blocks=blocks_lo, inodes=inodes, bpg=bpg, ipg=ipg,
                           fdb=fdb, rev=rev, vol=vol, state=state, total=total,
                           magic_abs=MTK8+j)

items = sorted(found.values(), key=lambda d: d['fs_start'])
print(f"Real ext4 superblocks found: {len(items)}")
print(f"{'#':>3} {'fs_start(rel)':>12} {'abs':>10} {'blk_sz':>7} {'blocks':>9} {'total':>12} {'rev':>3} {'state':>5} {'inodes':>8} {'vol':>16}")
for k, d in enumerate(items):
    print(f"{k:>3} {d['fs_start']:>12} {MTK8+d['fs_start']:>10} {d['block_size']:>7} {d['blocks']:>9} {d['total']:>12} {d['rev']:>3} {d['state']:>5} {d['inodes']:>8} '{d['vol']}'")
