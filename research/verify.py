import struct, sys, mmap, ctypes, re
from ctypes import wintypes

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
    b, sz, _, _, nrva = struct.unpack_from('<QIIII', m, r + 4 + i * 108)
    mods.append((b, sz, mdstr(nrva).split('\\')[-1]))
ranges = []
s, r = streams[5][0]
for i in range(struct.unpack_from('<I', m, r)[0]):
    st, sz, rv = struct.unpack_from('<QII', m, r + 4 + i * 16)
    ranges.append((st, sz, rv))
ranges.sort()


def read(a, n):
    for st, sz, off in ranges:
        if st <= a < st + sz:
            return m[off + a - st:off + a - st + min(n, st + sz - a)]
    return b''


def q(a):
    b = read(a, 8)
    return struct.unpack('<Q', b)[0] if len(b) == 8 else None


def sym(a):
    if a is None:
        return ''
    for b, sz, nm in mods:
        if b <= a < b + sz:
            return '%s+0x%x' % (nm, a - b)
    return ''


base = [b for b, s_, n in mods if n.lower().startswith('capcomarcade2nd')][0]
s, r = streams[6][0]
ctx_size, ctx_rva = struct.unpack_from('<II', m, r + 8 + 152)
crash_rsp = struct.unpack_from('<Q', m, ctx_rva + 0x98)[0]
frame = crash_rsp + 0x40
rbp = frame + 0x100
print('return addr slot:', hex(q(frame + 0x4e8)), sym(q(frame + 0x4e8)))
for i in range(5):
    a = rbp + 0x390 + i * 8
    v = q(a)
    vt = q(v) if v else None
    print('arr[%d] @rbp+%x = %s  vtable=%s %s' % (i, 0x390 + i * 8, hex(v) if v else v, hex(vt) if vt else vt, sym(vt)))
gc = q(base + 0x6f0b4c8)
print('global cookie', hex(gc), ' expected slot value', hex(gc ^ frame), ' actual', hex(q(rbp + 0x3b0)))

img = b''.join(m[off:off + sz] for st, sz, off in ranges if st - base == 0x1000)
print('--- image strings')
for o in (0x51c5100, 0x51c5160):
    print(hex(o), read(base + o, 96).split(b'\0')[0])
print('--- same-shaped loops (cmp ebx,4 / jae) in image')
for mt in re.finditer(rb'\x83\xfb\x04\x73.{1,60}?\xff\x57\x38', img, re.S):
    print('  ', hex(mt.start() + 0x1000))

print('--- live DXGI enumeration')
dxgi = ctypes.WinDLL('dxgi')
iid = (ctypes.c_ubyte * 16).from_buffer_copy(bytes.fromhex('7b7166ec2ec7b24ec7bfc4d3e0a55f22')[:0] or
    struct.pack('<IHH8B', 0x770aae78, 0xf26f, 0x4dba, 0xa8, 0x29, 0x25, 0x3c, 0x83, 0xd1, 0xb3, 0x87))
fac = ctypes.c_void_p()
hr = dxgi.CreateDXGIFactory1(ctypes.byref(iid), ctypes.byref(fac))
print('factory hr', hex(hr & 0xffffffff))


def vcall(obj, idx, restype, *argtypes):
    vt = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vt[idx])


class DESC(ctypes.Structure):
    _fields_ = [('Description', ctypes.c_wchar * 128), ('VendorId', ctypes.c_uint), ('DeviceId', ctypes.c_uint),
                ('SubSysId', ctypes.c_uint), ('Revision', ctypes.c_uint), ('V', ctypes.c_size_t), ('S', ctypes.c_size_t),
                ('SS', ctypes.c_size_t), ('Luid', ctypes.c_longlong)]


i = 0
while True:
    SENT = 0x4141414141414141
    p = ctypes.c_ulonglong(SENT)
    hr = vcall(fac, 7, ctypes.c_long, ctypes.c_uint, ctypes.POINTER(ctypes.c_ulonglong))(fac, i, ctypes.byref(p)) & 0xffffffff
    if hr == 0x887a0002:
        print('index', i, 'NOT_FOUND; out-param after call =', hex(p.value), '(sentinel kept)' if p.value == SENT else '(OVERWRITTEN)')
        break
    d = DESC()
    a = ctypes.c_void_p(p.value)
    vcall(a, 8, ctypes.c_long, ctypes.POINTER(DESC))(a, ctypes.byref(d))
    print('index', i, repr(d.Description), 'ven %04x dev %04x' % (d.VendorId, d.DeviceId))
    vcall(a, 2, ctypes.c_ulong)(a)
    i += 1
