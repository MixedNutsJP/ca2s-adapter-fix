"""List the code around every other DXGI_ERROR_NOT_FOUND comparison in a dump.

Used to check whether the off-by-one at 0x25E82B0 is the only one. For each site
it prints the disassembly leading up to the comparison.

usage: python -I research/enum_sites.py <dump> <capstone-pylib-dir>
"""
import mmap
import re
import struct
import sys

sys.path.insert(0, sys.argv[2])
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

SITES = [0x23427f2, 0x2342845, 0x25d610d, 0x25e9596]
BACK = 0xB0
FORWARD = 0x60

f = open(sys.argv[1], 'rb')
m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
_, _, n, rva = struct.unpack_from('<IIII', m, 0)
streams = {}
for i in range(n):
    t, s, r = struct.unpack_from('<III', m, rva + i * 12)
    streams.setdefault(t, []).append((s, r))


def mdstr(r):
    k = struct.unpack_from('<I', m, r)[0]
    return m[r + 4:r + 4 + k].decode('utf-16-le', 'replace')


s, r = streams[4][0]
mods = []
for i in range(struct.unpack_from('<I', m, r)[0]):
    b, sz, _, _, nr = struct.unpack_from('<QIIII', m, r + 4 + i * 108)
    mods.append((b, sz, mdstr(nr).split(chr(92))[-1]))

ranges = []
if 9 in streams:
    s, r = streams[9][0]
    cnt, o = struct.unpack_from('<QQ', m, r)
    for i in range(cnt):
        a, z = struct.unpack_from('<QQ', m, r + 16 + i * 16)
        ranges.append((a, z, o))
        o += z
if 5 in streams:
    s, r = streams[5][0]
    for i in range(struct.unpack_from('<I', m, r)[0]):
        a, z, o = struct.unpack_from('<QII', m, r + 4 + i * 16)
        ranges.append((a, z, o))
ranges.sort()


def read(a, k):
    for st, z, o in ranges:
        if st <= a < st + z:
            return bytes(m[o + a - st:o + a - st + min(k, st + z - a)])
    return b''


base = [b for b, _, x in mods if x.lower().startswith('capcomarcade2nd')][0]
md = Cs(CS_ARCH_X86, CS_MODE_64)

for site in SITES:
    print(f'\n=== site +{site:x}')
    start = base + site - BACK
    code = read(start, BACK + FORWARD)
    # Sync the linear sweep: try offsets until one lands exactly on the cmp.
    target = base + site - 1  # imm32 follows the 3d opcode of "cmp eax, imm32"
    chosen = None
    for off in range(0, 0x40):
        addrs = [i.address for i in md.disasm(code[off:], start + off)]
        if target in addrs or target - 1 in addrs or target - 2 in addrs:
            chosen = off
            break
    if chosen is None:
        print('  could not sync')
        continue
    for i in md.disasm(code[chosen:], start + chosen):
        line = f'{i.address - base:x}: {i.mnemonic} {i.op_str}'
        mt = re.search(r'rip \+ (0x[0-9a-f]+)', i.op_str)
        if mt:
            t = i.address + i.size + int(mt.group(1), 16)
            line += f' ; [{t - base:x}]'
        print(line)
