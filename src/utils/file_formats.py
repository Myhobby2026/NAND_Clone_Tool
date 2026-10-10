"""
File Format Handlers
====================
Handlers for reading and writing NAND Flash dump files.

Supported formats:
  1. Raw Binary (.bin)          — plain page data, no header
  2. NAND Image (.nandimg)      — custom format with metadata header
  3. Raw Image (.img)           — same as .bin for compatibility
  4. Intel Hex (.hex)           — for small SLC chips
"""

from __future__ import annotations

import io
import os
import json
import struct
import hashlib
import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, Iterator, BinaryIO

from ..models.nand_models import DeviceInfo


# ─────────────────────────────────────────────────────────────
#  .nandimg custom format
# ─────────────────────────────────────────────────────────────
#
# File structure:
#   [MAGIC:8][VERSION:2][HDR_LEN:4][HEADER_JSON:HDR_LEN][DATA:...]
#
# Magic: b"NANDIMG\x00"
# Header JSON fields: see NANDImageHeader

NANDIMG_MAGIC   = b"NANDIMG\x00"
NANDIMG_VERSION = 0x0100  # 1.0


@dataclass
class NANDImageHeader:
    """Metadata header for the .nandimg format."""
    version:         str   = "1.0"
    created_at:      str   = ""
    tool_version:    str   = "1.0.0"
    
    # Device info
    manufacturer:    str   = "Unknown"
    model:           str   = "Unknown"
    mfr_id:          int   = 0
    dev_id:          int   = 0
    id_bytes:        str   = ""
    
    # Geometry
    page_size:       int   = 2048
    oob_size:        int   = 64
    pages_per_block: int   = 64
    blocks_per_lun:  int   = 1024
    luns:            int   = 1
    total_pages:     int   = 0
    total_size:      int   = 0
    
    # Dump info
    include_oob:     bool  = False
    ecc_applied:     bool  = True
    ecc_mode:        str   = "hamming"
    
    # Integrity
    bad_blocks:      list  = field(default_factory=list)
    sha256:          str   = ""
    
    def to_json(self) -> bytes:
        d = asdict(self)
        return json.dumps(d, indent=2).encode("utf-8")
    
    @classmethod
    def from_json(cls, data: bytes) -> "NANDImageHeader":
        d = json.loads(data.decode("utf-8"))
        obj = cls()
        for k, v in d.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        return obj

    @classmethod
    def from_device(cls, dev: DeviceInfo,
                    include_oob: bool = False,
                    ecc_mode: str = "hamming") -> "NANDImageHeader":
        return cls(
            created_at      = datetime.datetime.now().isoformat(),
            manufacturer    = dev.manufacturer,
            model           = dev.model,
            mfr_id          = dev.mfr_id,
            dev_id          = dev.dev_id,
            id_bytes        = " ".join(f"{b:02X}" for b in dev.id_bytes),
            page_size       = dev.page_size,
            oob_size        = dev.oob_size,
            pages_per_block = dev.pages_per_block,
            blocks_per_lun  = dev.blocks_per_lun,
            luns            = dev.luns,
            total_pages     = dev.total_pages,
            total_size      = dev.total_size_bytes,
            include_oob     = include_oob,
            ecc_mode        = ecc_mode,
        )


# ─────────────────────────────────────────────────────────────
#  .nandimg Writer
# ─────────────────────────────────────────────────────────────
class NANDImageWriter:
    """Write data to .nandimg format with metadata header."""

    def __init__(self, path: str, header: NANDImageHeader):
        self.path   = path
        self.header = header
        self._file: Optional[BinaryIO] = None
        self._hasher = hashlib.sha256()
        self._bytes_written = 0

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    def open(self):
        self._file = open(self.path, "wb")
        # Write placeholder header (will be updated on close)
        hdr_json  = self.header.to_json()
        hdr_len   = len(hdr_json)
        
        self._file.write(NANDIMG_MAGIC)
        self._file.write(struct.pack("<H", NANDIMG_VERSION))
        self._file.write(struct.pack("<I", hdr_len))
        self._file.write(hdr_json)
        
        self._data_offset = self._file.tell()

    def write_page(self, data: bytes):
        """Write one page of data."""
        self._file.write(data)
        self._hasher.update(data)
        self._bytes_written += len(data)

    def close(self):
        if not self._file:
            return
        
        # Update SHA256 in header
        self.header.sha256 = self._hasher.hexdigest()
        
        # Rewrite header with SHA256
        self._file.seek(0)
        hdr_json = self.header.to_json()
        hdr_len  = len(hdr_json)
        
        self._file.write(NANDIMG_MAGIC)
        self._file.write(struct.pack("<H", NANDIMG_VERSION))
        self._file.write(struct.pack("<I", hdr_len))
        self._file.write(hdr_json)
        
        self._file.close()
        self._file = None


# ─────────────────────────────────────────────────────────────
#  .nandimg Reader
# ─────────────────────────────────────────────────────────────
class NANDImageReader:
    """Read .nandimg files with metadata and integrity check."""

    def __init__(self, path: str):
        self.path   = path
        self.header: Optional[NANDImageHeader] = None
        self._data_offset = 0
        self._file: Optional[BinaryIO] = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    def open(self) -> bool:
        self._file = open(self.path, "rb")
        
        # Read magic
        magic = self._file.read(8)
        if magic != NANDIMG_MAGIC:
            self._file.close()
            raise ValueError(f"Not a valid .nandimg file (bad magic: {magic!r})")
        
        # Read version and header length
        version = struct.unpack("<H", self._file.read(2))[0]
        hdr_len = struct.unpack("<I", self._file.read(4))[0]
        
        hdr_json = self._file.read(hdr_len)
        self.header = NANDImageHeader.from_json(hdr_json)
        self._data_offset = self._file.tell()
        return True

    def read_page(self, page_num: int) -> bytes:
        if not self._file or not self.header:
            raise RuntimeError("File not opened")
        
        page_total = (self.header.page_size +
                      (self.header.oob_size if self.header.include_oob else 0))
        offset = self._data_offset + page_num * page_total
        self._file.seek(offset)
        return self._file.read(page_total)

    def iter_pages(self) -> Iterator[tuple[int, bytes]]:
        """Iterate over all pages, yielding (page_num, data)."""
        if not self._file or not self.header:
            return
        self._file.seek(self._data_offset)
        page_total = (self.header.page_size +
                      (self.header.oob_size if self.header.include_oob else 0))
        page_num = 0
        while True:
            data = self._file.read(page_total)
            if len(data) < page_total:
                break
            yield page_num, data
            page_num += 1

    def verify_sha256(self) -> bool:
        """Verify SHA256 of data area."""
        if not self.header or not self.header.sha256:
            return False
        hasher = hashlib.sha256()
        self._file.seek(self._data_offset)
        while True:
            chunk = self._file.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
        return hasher.hexdigest() == self.header.sha256

    def close(self):
        if self._file:
            self._file.close()
            self._file = None


# ─────────────────────────────────────────────────────────────
#  Raw Binary (.bin / .img) Format
# ─────────────────────────────────────────────────────────────
class RawBinaryWriter:
    """Write raw binary dump (no metadata header)."""

    def __init__(self, path: str):
        self.path  = path
        self._file: Optional[BinaryIO] = None

    def __enter__(self):
        self._file = open(self.path, "wb")
        return self

    def __exit__(self, *args):
        if self._file:
            self._file.close()

    def write_page(self, data: bytes):
        self._file.write(data)


class RawBinaryReader:
    """Read raw binary dump file."""

    def __init__(self, path: str, page_size: int, oob_size: int = 0):
        self.path      = path
        self.page_size = page_size
        self.oob_size  = oob_size
        self.file_size = os.path.getsize(path)
        self._total_pages = self.file_size // (page_size + oob_size) if page_size > 0 else 0

    @property
    def total_pages(self) -> int:
        return self._total_pages

    def read_page(self, page_num: int) -> Optional[bytes]:
        stride = self.page_size + self.oob_size
        offset = page_num * stride
        if offset >= self.file_size:
            return None
        with open(self.path, "rb") as f:
            f.seek(offset)
            return f.read(stride)

    def iter_pages(self) -> Iterator[tuple[int, bytes]]:
        stride = self.page_size + self.oob_size
        with open(self.path, "rb") as f:
            page_num = 0
            while True:
                data = f.read(stride)
                if len(data) < stride:
                    break
                yield page_num, data
                page_num += 1


# ─────────────────────────────────────────────────────────────
#  Format Detector
# ─────────────────────────────────────────────────────────────
def detect_file_format(path: str) -> str:
    """Auto-detect the file format of a NAND dump file."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".nandimg":
        try:
            with open(path, "rb") as f:
                magic = f.read(8)
            if magic == NANDIMG_MAGIC:
                return "nandimg"
        except OSError:
            pass
    elif ext in (".hex",):
        return "intel_hex"
    # Default: raw binary
    return "raw"


def open_dump_for_reading(path: str,
                           page_size: int = 2048,
                           oob_size:  int = 64):
    """
    Open a NAND dump file for reading.
    Returns (reader, header_or_None).
    """
    fmt = detect_file_format(path)
    if fmt == "nandimg":
        reader = NANDImageReader(path)
        reader.open()
        return reader, reader.header
    else:
        reader = RawBinaryReader(path, page_size, oob_size)
        return reader, None


def create_dump_writer(path: str, fmt: str,
                        header: Optional[NANDImageHeader] = None):
    """
    Create a dump writer.
    fmt: 'nandimg' | 'raw'
    """
    if fmt == "nandimg":
        if header is None:
            header = NANDImageHeader()
        return NANDImageWriter(path, header)
    else:
        return RawBinaryWriter(path)
