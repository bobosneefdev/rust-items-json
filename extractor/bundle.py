"""Byte-range access to Rust's UnityFS bundles.

Rust ships its bundles with uncompressed blocks, so every node inside a bundle
(the serialized index and its `.resS` texture data) is a plain byte range in the
file. Reading those ranges directly keeps memory flat: the texture bundles are
6-7 GB each, but an icon needs only its own few KB.
"""

import mmap
import struct
from pathlib import Path

import lz4.block
from UnityPy.files import SerializedFile
from UnityPy.streams import EndianBinaryReader


def _cstr(f) -> str:
    b = bytearray()
    while (c := f.read(1)) != b"\0":
        b += c
    return b.decode()


class Bundle:
    def __init__(self, path: Path):
        self.path = path
        self.nodes: dict[str, tuple[int, int]] = {}
        with open(path, "rb") as f:
            if _cstr(f) != "UnityFS":
                raise ValueError(f"{path}: not a UnityFS bundle")
            f.read(4)
            _cstr(f)
            _cstr(f)
            _size, csz, usz, flags = struct.unpack(">qIII", f.read(20))
            if flags & 0x80:
                raise ValueError(f"{path}: block info at end of file is not supported")
            if flags & 0x200:
                f.seek((f.tell() + 15) // 16 * 16)
            raw = f.read(csz)
            info = raw if flags & 0x3F == 0 else lz4.block.decompress(raw, uncompressed_size=usz)
            data_start = f.tell()
            if flags & 0x200:
                data_start = (data_start + 15) // 16 * 16

        p = 16
        (nb,) = struct.unpack(">i", info[p : p + 4])
        p += 4
        for i in range(nb):
            _u, _c, fl = struct.unpack(">IIH", info[p + i * 10 : p + i * 10 + 10])
            if fl & 0x3F:
                raise ValueError(f"{path}: compressed blocks are not supported")
        p += nb * 10
        (nn,) = struct.unpack(">i", info[p : p + 4])
        p += 4
        for _ in range(nn):
            off, sz, _fl = struct.unpack(">qqI", info[p : p + 20])
            p += 20
            e = info.index(b"\0", p)
            self.nodes[info[p:e].decode()] = (data_start + off, sz)
            p = e + 1

        self._fh = open(path, "rb")
        self._mm = mmap.mmap(self._fh.fileno(), 0, access=mmap.ACCESS_READ)

    @property
    def cab(self) -> str:
        return next(n for n in self.nodes if not n.endswith((".resS", ".resource")))

    def serialized(self) -> SerializedFile:
        off, size = self.nodes[self.cab]
        return SerializedFile(EndianBinaryReader(memoryview(self._mm)[off : off + size]), name=self.cab)

    def read(self, node: str, offset: int, size: int) -> bytes:
        base, total = self.nodes[node]
        if offset + size > total:
            raise ValueError(f"{node}: read past end")
        return self._mm[base + offset : base + offset + size]
