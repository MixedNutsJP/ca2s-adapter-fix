import struct, sys, re, mmap

path = sys.argv[1]
f = open(path, 'rb')
m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

sig, ver, nstreams, rva, cksum, ts, flags = struct.unpack_from('<IIIIIIQ', m, 0)
print('flags', hex(flags), 'streams', nstreams)
streams = {}
for i in range(nstreams):
    t, size, r = struct.unpack_from('<III', m, rva + i * 12)
    streams.setdefault(t, []).append((size, r))
print('stream types', sorted(streams))


def mdstr(r):
    n = struct.unpack_from('<I', m, r)[0]
    return m[r + 4:r + 4 + n].decode('utf-16-le', 'replace')


mods = []
s, r = streams[4][0]
n = struct.unpack_from('<I', m, r)[0]
for i in range(n):
    base, size, _, _, nrva = struct.unpack_from('<QIIII', m, r + 4 + i * 108)
    mods.append((base, size, mdstr(nrva)))
mods.sort()


def sym(a):
    for b, sz, nm in mods:
        if b <= a < b + sz:
            return '%s+0x%x' % (nm.split('\\')[-1], a - b)
    return None


# memory ranges
ranges = []
if 9 in streams:
    s, r = streams[9][0]
    cnt, base_rva = struct.unpack_from('<QQ', m, r)
    off = base_rva
    for i in range(cnt):
        st, sz = struct.unpack_from('<QQ', m, r + 16 + i * 16)
        ranges.append((st, sz, off))
        off += sz
if 5 in streams:
    s, r = streams[5][0]
    cnt = struct.unpack_from('<I', m, r)[0]
    for i in range(cnt):
        st, sz, rv = struct.unpack_from('<QII', m, r + 4 + i * 16)
        ranges.append((st, sz, rv))
ranges.sort()
print('mem ranges', len(ranges), 'bytes', sum(x[1] for x in ranges))


def read(a, n):
    for st, sz, off in ranges:
        if st <= a < st + sz:
            n2 = min(n, st + sz - a)
            return m[off + a - st:off + a - st + n2]
    return b''


s, r = streams[6][0]
tid, _ = struct.unpack_from('<II', m, r)
code, eflags, rec, addr, np_, _ = struct.unpack_from('<IIQQII', m, r + 8)
params = struct.unpack_from('<15Q', m, r + 8 + 32)
ctx_size, ctx_rva = struct.unpack_from('<II', m, r + 8 + 152)
print('thread', tid, 'code', hex(code), 'addr', hex(addr), sym(addr), 'params', [hex(p) for p in params[:np_]])
rsp = struct.unpack_from('<Q', m, ctx_rva + 0x98)[0]
rip = struct.unpack_from('<Q', m, ctx_rva + 0xF8)[0]
print('rsp', hex(rsp), 'rip', hex(rip), sym(rip))

data = read(rsp, 0x8000)
print('stack bytes', len(data))
print('--- code pointers on faulting stack')
shown = 0
for i in range(0, len(data) - 8, 8):
    v = struct.unpack_from('<Q', data, i)[0]
    sy = sym(v)
    if sy:
        print('  rsp+%05x %016x %s' % (i, v, sy))
        shown += 1
        if shown > 120:
            break

print('--- strings on faulting stack')
seen = set()
for mt in re.finditer(rb'[\x20-\x7e]{6,}', data):
    t = mt.group().decode()
    if t not in seen:
        seen.add(t)
        print('  a +%05x %s' % (mt.start(), t[:160]))
for mt in re.finditer(rb'(?:[\x20-\x7e]\x00){5,}', data):
    t = mt.group().decode('utf-16-le')
    if t not in seen:
        seen.add(t)
        print('  w +%05x %s' % (mt.start(), t[:160]))

print('--- other modules outside system/steam/nv')
for b, sz, nm in mods:
    if not re.search(r'\\windows\\|\\steam\\', nm, re.I):
        print(' ', hex(b), nm)
print('--- system info')
s, r = streams[7][0]
arch, lvl, rev, ncpu, ptype = struct.unpack_from('<HHHBB', m, r)
print('arch', arch, 'cpus', ncpu)
