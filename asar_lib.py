# -*- coding: utf-8 -*-
"""最小 asar 读写工具（无需 electron 依赖）"""
import json
import os
import struct


def read_header(path):
    with open(path, 'rb') as f:
        size_pickle = f.read(8)
        # pickle: [type=4(4byte)][payload=uint32]
        hsize = struct.unpack('<I', size_pickle[4:8])[0]
        header_buf = f.read(hsize)
        # header pickle: [payload_len(4)][strlen(4)][string]
        strlen = struct.unpack('<I', header_buf[4:8])[0]
        header = json.loads(header_buf[8:8 + strlen].decode('utf-8'))
        data_start = 8 + hsize
        return header, data_start


def list_files(path):
    """返回 [(相对路径, offset, size)]"""
    header, data_start = read_header(path)
    out = []

    def walk(node, prefix):
        for name, meta in node.get('files', {}).items():
            p = prefix + name
            if 'files' in meta:
                walk(meta, p + '/')
            else:
                if not meta.get('unpacked'):
                    out.append((p, int(meta.get('offset', 0)) + data_start,
                                int(meta.get('size', 0))))
    walk(header, '')
    return out


def extract(path, member, dest):
    for p, off, sz in list_files(path):
        if p == member:
            with open(path, 'rb') as f:
                f.seek(off)
                data = f.read(sz)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, 'wb') as w:
                w.write(data)
            return len(data)
    return -1


def extract_all(path, outdir):
    n = 0
    with open(path, 'rb') as f:
        for p, off, sz in list_files(path):
            f.seek(off)
            data = f.read(sz)
            dest = os.path.join(outdir, p.replace('/', os.sep))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, 'wb') as w:
                w.write(data)
            n += 1
    return n


def pack(srcdir, outpath, chunk_size=4 * 1024 * 1024):
    """把目录打包成 asar（保持 electron 兼容的 header 格式）"""
    files_meta = {}

    def add(path_prefix, rel, meta):
        parts = rel.split('/')
        node = meta
        for part in parts[:-1]:
            node = node.setdefault('files', {}).setdefault(part, {'files': {}})
        node.setdefault('files', {})[parts[-1]] = {}

    entries = []
    for root, _, names in os.walk(srcdir):
        for name in names:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, srcdir).replace(os.sep, '/')
            entries.append((rel, full))
    entries.sort()

    blobs = []
    offset = 0
    for rel, full in entries:
        size = os.path.getsize(full)
        node = files_meta
        parts = rel.split('/')
        for part in parts[:-1]:
            node = node.setdefault('files', {}).setdefault(part, {'files': {}})
        node.setdefault('files', {})[parts[-1]] = {
            'size': size, 'offset': str(offset)}
        with open(full, 'rb') as f:
            blobs.append(f.read())
        offset += size

    header_json = json.dumps({'files': files_meta}, ensure_ascii=False)
    hb = header_json.encode('utf-8')
    # header pickle: [4-byte len][string]
    header_buf = struct.pack('<I', len(hb)) + hb
    # 8 + len(header_buf) must be multiple of 4
    pad = (4 - (len(header_buf) % 4)) % 4
    header_buf += b'\x00' * pad
    # size pickle: [4][hsize]
    size_pickle = struct.pack('<II', 4, len(header_buf))

    with open(outpath, 'wb') as f:
        f.write(size_pickle)
        f.write(header_buf)
        for b in blobs:
            f.write(b)
    return outpath, len(blobs)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("usage: asar_lib.py list <asar> | extract <asar> <member> <dest> | xall <asar> <dir>")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'list':
        for p, off, sz in list_files(sys.argv[2]):
            print(f'{sz:>10,}  {p}')
    elif cmd == 'extract':
        print(extract(sys.argv[2], sys.argv[3], sys.argv[4]))
    elif cmd == 'xall':
        print(extract_all(sys.argv[2], sys.argv[3]))
