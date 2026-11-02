import struct, sys, mmap, re
sys.path.insert(0, sys.argv[2])
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

path = sys.argv[1]
f = open(path, 'rb')
m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
sig, ver, nstreams, rva, cksum, ts, flags = struct.unpack_from('<IIIIIIQ', m, 0)
streams = {}
for i in range(nstreams):
    t, size, r = struct.unpack_from('<III', m, rva + i * 12)
    streams.setdefault(t, []).append((size, r))


def mdstr(r):
    n = struct.unpack_from('<I', m, r)[0]
    return m[r + 4:r + 4 + n].decode('utf-16-le', 'replace')


mods = []
s, r = streams[4][0]
for i in range(struct.unpack_from('<I', m, r)[0]):
    base, size, _, _, nrva = struct.unpack_from('<QIIII', m, r + 4 + i * 108)
    mods.append((base, size, mdstr(nrva).split('\\')[-1]))
ranges = []
s, r = streams[5][0]
for i in range(struct.unpack_from('<I', m, r)[0]):
    st, sz, rv = struct.unpack_from('<QII', m, r + 4 + i * 16)
    ranges.append((st, sz, rv))
ranges.sort()
print('ranges', len(ranges))


def read(a, n):
    for st, sz, off in ranges:
        if st <= a < st + sz:
            return m[off + a - st:off + a - st + min(n, st + sz - a)]
    return b''


base = [b for b, s_, n in mods if n.lower().startswith('capcomarcade2nd')][0]
print('base', hex(base))
for st, sz, off in ranges:
    if base <= st < base + 0x10000000 and sz > 0x1000:
        print('  image range +%x size %x' % (st - base, sz))

ret = base + 0x25e87b6
code = read(ret - 0x3000, 0x3400)
print('code around ret', len(code))
if not code:
    code = read(ret - 0x100, 0x200)
    print('short', len(code))
md = Cs(CS_ARCH_X86, CS_MODE_64)
start = ret - 0x3000 if len(code) > 0x200 else ret - 0x100

# function prologue: walk back to the nearest CC padding before the return address
buf_off = ret - start
pos = buf_off
while pos > 8 and not (code[pos - 1] == 0xCC and code[pos - 2] == 0xCC):
    pos -= 1
fn = start + pos
print('function start guess +%x, size %x' % (fn - base, ret - fn))
for ins in md.disasm(code[pos:buf_off + 0x20], fn):
    t = ''
    mt = re.search(r'rip \+ (0x[0-9a-f]+)', ins.op_str)
    if mt:
        tgt = ins.address + ins.size + int(mt.group(1), 16)
        t = ' ; [%x]' % (tgt - base if base <= tgt < base + 0x10000000 else tgt)
        b = read(tgt, 8)
        if len(b) == 8:
            v = struct.unpack('<Q', b)[0]
            for mb, msz, nm in mods:
                if mb <= v < mb + msz:
                    t += ' -> %s+0x%x' % (nm, v - mb)
    print('%x: %s %s%s' % (ins.address - base, ins.mnemonic, ins.op_str, t))
