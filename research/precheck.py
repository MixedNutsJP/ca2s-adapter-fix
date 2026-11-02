import mmap, struct, sys

path = sys.argv[1]
f = open(path, 'rb')
m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
pe = struct.unpack_from('<I', m, 0x3c)[0]
nsec = struct.unpack_from('<H', m, pe + 6)[0]
optsz = struct.unpack_from('<H', m, pe + 20)[0]
print('ImageBase', hex(struct.unpack_from('<Q', m, pe + 24 + 24)[0]), 'SizeOfImage', hex(struct.unpack_from('<I', m, pe + 24 + 56)[0]), 'TimeDateStamp', hex(struct.unpack_from('<I', m, pe + 8)[0]))
secs = []
for i in range(nsec):
    o = pe + 24 + optsz + i * 40
    name = m[o:o + 8].rstrip(b'\0').decode('latin1')
    vs, va, rs, rp = struct.unpack_from('<IIII', m, o + 8)
    ch = struct.unpack_from('<I', m, o + 36)[0]
    secs.append((name, va, vs, rp, rs))
    print('%-10s va=%08x vsize=%08x raw=%08x rawsize=%08x ch=%08x' % (name, va, vs, rp, rs, ch))

rva = 0x25e82b0
for name, va, vs, rp, rs in secs:
    if va <= rva < va + vs:
        off = rva - va + rp
        print('RVA in', name, 'file bytes', m[off:off + 16].hex() if rva - va < rs else 'outside raw data')
pat = bytes.fromhex('83fb047322')
print('pattern hits in file', m.find(pat))

# import table names mentioning dxgi / d3d (only readable if not packed)
print('b"dxgi.dll" offset', m.find(b'dxgi.dll'), ' b"DXGI.dll"', m.find(b'DXGI.dll'), ' CreateDXGIFactory', m.find(b'CreateDXGIFactory'))
