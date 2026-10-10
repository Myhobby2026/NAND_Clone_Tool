"""
NAND Flash Chip Database
========================
Comprehensive database of NAND Flash chips from major manufacturers.
Covers Samsung, Micron, Toshiba/Kioxia, SK Hynix, SanDisk/WD.

Each entry contains:
  - Manufacturer/Device IDs
  - Geometry (page, block, density)
  - Timing parameters
  - ECC requirements
  - Package information
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
import json


# ─────────────────────────────────────────────────────────────
#  Enums / Constants
# ─────────────────────────────────────────────────────────────
MANUFACTURER_IDS: Dict[int, str] = {
    0x01: "AMD/Spansion",
    0x04: "Fujitsu",
    0x07: "Renesas",
    0x08: "STMicro / Numonyx",
    0x20: "STMicro / Micron",
    0x2C: "Micron Technology",
    0x45: "SanDisk",
    0x89: "Intel",
    0x92: "EON Silicon",
    0x98: "Toshiba / Kioxia",
    0xAD: "SK Hynix",
    0xC2: "Macronix",
    0xC8: "ESMT",
    0xD3: "Nanya Technology",
    0xEC: "Samsung Electronics",
}

# Cell type strings
CELL_TYPES = {1: "SLC", 2: "MLC", 3: "TLC", 4: "QLC"}


# ─────────────────────────────────────────────────────────────
#  Data Classes
# ─────────────────────────────────────────────────────────────
@dataclass
class NANDTimings:
    """NAND Flash timing parameters (nanoseconds)."""
    t_wp:   int = 12    # WE# pulse width
    t_rp:   int = 12    # RE# pulse width
    t_rea:  int = 25    # RE# access time
    t_wc:   int = 25    # Write cycle time
    t_rc:   int = 25    # Read cycle time
    t_prog: int = 300   # Max program time (µs)
    t_bers: int = 3000  # Max block erase time (µs)
    t_r:    int = 200   # Max page read time (µs)


@dataclass
class NANDChipInfo:
    """Complete NAND Flash chip information."""
    # Identity
    manufacturer:      str
    part_number:       str
    description:       str
    mfr_id:            int
    dev_id:            int
    id_bytes:          Tuple[int, ...]  # Full 5-8 byte ID sequence

    # Geometry
    page_size:         int              # Bytes (data area)
    oob_size:          int              # Bytes (spare area)
    pages_per_block:   int
    blocks_per_lun:    int
    luns_per_die:      int = 1
    dies_per_package:  int = 1

    # Electrical
    cell_type:         int = 1          # 1=SLC, 2=MLC, 3=TLC, 4=QLC
    bits_per_cell:     int = 1
    col_addr_cycles:   int = 2
    row_addr_cycles:   int = 3
    bus_width:         int = 8          # 8 or 16

    # ECC
    ecc_bits_required: int = 1          # Bits correctable per 512B
    ecc_sector_size:   int = 512        # ECC sector size in bytes

    # Timing
    timings:           NANDTimings = field(default_factory=NANDTimings)

    # Package
    package:           str = "TSOP48"
    voltage_vcc:       float = 3.3
    voltage_vccq:      float = 1.8

    # Features
    onfi_version:      Optional[str] = None
    supports_cache:    bool = False
    supports_multiplane: bool = False

    @property
    def block_size_bytes(self) -> int:
        return self.page_size * self.pages_per_block

    @property
    def lun_size_bytes(self) -> int:
        return self.block_size_bytes * self.blocks_per_lun

    @property
    def total_size_bytes(self) -> int:
        return self.lun_size_bytes * self.luns_per_die * self.dies_per_package

    @property
    def total_pages(self) -> int:
        return self.pages_per_block * self.blocks_per_lun * self.luns_per_die * self.dies_per_package

    @property
    def total_blocks(self) -> int:
        return self.blocks_per_lun * self.luns_per_die * self.dies_per_package

    @property
    def density_gbit(self) -> float:
        return self.total_size_bytes / (1024**3) * 8

    @property
    def cell_type_str(self) -> str:
        return CELL_TYPES.get(self.cell_type, "Unknown")

    def to_dict(self) -> dict:
        return {
            "manufacturer":      self.manufacturer,
            "part_number":       self.part_number,
            "description":       self.description,
            "mfr_id":            f"0x{self.mfr_id:02X}",
            "dev_id":            f"0x{self.dev_id:02X}",
            "id_bytes":          [f"0x{b:02X}" for b in self.id_bytes],
            "page_size":         self.page_size,
            "oob_size":          self.oob_size,
            "pages_per_block":   self.pages_per_block,
            "blocks_per_lun":    self.blocks_per_lun,
            "luns_per_die":      self.luns_per_die,
            "dies_per_package":  self.dies_per_package,
            "cell_type":         self.cell_type_str,
            "bus_width":         self.bus_width,
            "ecc_bits_required": self.ecc_bits_required,
            "package":           self.package,
            "total_size_mb":     self.total_size_bytes // (1024 * 1024),
            "density_gbit":      round(self.density_gbit, 2),
        }


# ─────────────────────────────────────────────────────────────
#  Chip Database
# ─────────────────────────────────────────────────────────────
NAND_DATABASE: List[NANDChipInfo] = [

    # ═══════════════════════════════════════════════════════
    #  SAMSUNG
    # ═══════════════════════════════════════════════════════
    NANDChipInfo(
        manufacturer="Samsung", part_number="K9F1G08U0E",
        description="Samsung 1Gbit SLC NAND Flash",
        mfr_id=0xEC, dev_id=0xF1,
        id_bytes=(0xEC, 0xF1, 0x00, 0x95, 0x40),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=1024,
        cell_type=1, ecc_bits_required=1,
        timings=NANDTimings(t_prog=250, t_bers=2000),
    ),
    NANDChipInfo(
        manufacturer="Samsung", part_number="K9F2G08U0C",
        description="Samsung 2Gbit SLC NAND Flash",
        mfr_id=0xEC, dev_id=0xDA,
        id_bytes=(0xEC, 0xDA, 0x10, 0x95, 0x44),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=2048,
        cell_type=1, ecc_bits_required=1,
        timings=NANDTimings(t_prog=250, t_bers=2000),
    ),
    NANDChipInfo(
        manufacturer="Samsung", part_number="K9F4G08U0D",
        description="Samsung 4Gbit SLC NAND Flash",
        mfr_id=0xEC, dev_id=0xDC,
        id_bytes=(0xEC, 0xDC, 0x10, 0x95, 0x54),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=4096,
        cell_type=1, ecc_bits_required=1,
        row_addr_cycles=3, col_addr_cycles=2,
    ),
    NANDChipInfo(
        manufacturer="Samsung", part_number="K9G8G08U0M",
        description="Samsung 8Gbit MLC NAND Flash",
        mfr_id=0xEC, dev_id=0xD3,
        id_bytes=(0xEC, 0xD3, 0x51, 0x95, 0x58),
        page_size=4096, oob_size=128,
        pages_per_block=64, blocks_per_lun=4096,
        cell_type=2, ecc_bits_required=4,
        timings=NANDTimings(t_prog=600, t_bers=5000),
    ),
    NANDChipInfo(
        manufacturer="Samsung", part_number="K9GAG08U0E",
        description="Samsung 16Gbit MLC NAND Flash (2-plane)",
        mfr_id=0xEC, dev_id=0xD5,
        id_bytes=(0xEC, 0xD5, 0x14, 0xB6, 0x74),
        page_size=4096, oob_size=128,
        pages_per_block=128, blocks_per_lun=4096,
        luns_per_die=2,
        cell_type=2, ecc_bits_required=4,
        supports_multiplane=True,
        timings=NANDTimings(t_prog=600, t_bers=5000),
    ),
    NANDChipInfo(
        manufacturer="Samsung", part_number="K9LBG08U0M",
        description="Samsung 32Gbit MLC NAND Flash",
        mfr_id=0xEC, dev_id=0xD7,
        id_bytes=(0xEC, 0xD7, 0xD5, 0x29, 0x38),
        page_size=4096, oob_size=128,
        pages_per_block=128, blocks_per_lun=4096,
        luns_per_die=2,
        cell_type=2, ecc_bits_required=4,
    ),
    NANDChipInfo(
        manufacturer="Samsung", part_number="K9ABG08U0A",
        description="Samsung 64Gbit MLC NAND Flash",
        mfr_id=0xEC, dev_id=0xDE,
        id_bytes=(0xEC, 0xDE, 0xD5, 0x7A, 0x58),
        page_size=8192, oob_size=436,
        pages_per_block=128, blocks_per_lun=4096,
        luns_per_die=2,
        cell_type=2, ecc_bits_required=24, ecc_sector_size=1024,
        supports_multiplane=True, supports_cache=True,
    ),

    # ═══════════════════════════════════════════════════════
    #  MICRON
    # ═══════════════════════════════════════════════════════
    NANDChipInfo(
        manufacturer="Micron", part_number="MT29F1G08ABAEA",
        description="Micron 1Gbit SLC NAND Flash",
        mfr_id=0x2C, dev_id=0xF1,
        id_bytes=(0x2C, 0xF1, 0x80, 0x15, 0x40),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=1024,
        cell_type=1, ecc_bits_required=1,
        onfi_version="2.1",
    ),
    NANDChipInfo(
        manufacturer="Micron", part_number="MT29F2G08ABAFA",
        description="Micron 2Gbit SLC NAND Flash",
        mfr_id=0x2C, dev_id=0xDA,
        id_bytes=(0x2C, 0xDA, 0x90, 0x95, 0x40),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=2048,
        cell_type=1, ecc_bits_required=1,
        onfi_version="2.1",
    ),
    NANDChipInfo(
        manufacturer="Micron", part_number="MT29F4G08ABADA",
        description="Micron 4Gbit SLC NAND Flash",
        mfr_id=0x2C, dev_id=0xDC,
        id_bytes=(0x2C, 0xDC, 0x90, 0x95, 0x54),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=4096,
        cell_type=1, ecc_bits_required=1,
        onfi_version="2.1",
    ),
    NANDChipInfo(
        manufacturer="Micron", part_number="MT29F8G08ABACA",
        description="Micron 8Gbit MLC NAND Flash",
        mfr_id=0x2C, dev_id=0xD3,
        id_bytes=(0x2C, 0xD3, 0x90, 0xA6, 0x64),
        page_size=4096, oob_size=224,
        pages_per_block=64, blocks_per_lun=4096,
        cell_type=2, ecc_bits_required=4,
        onfi_version="2.1", supports_multiplane=True,
    ),
    NANDChipInfo(
        manufacturer="Micron", part_number="MT29F16G08CBACA",
        description="Micron 16Gbit MLC NAND Flash",
        mfr_id=0x2C, dev_id=0x48,
        id_bytes=(0x2C, 0x48, 0x04, 0x46, 0x85),
        page_size=4096, oob_size=224,
        pages_per_block=256, blocks_per_lun=1024,
        luns_per_die=2,
        cell_type=2, ecc_bits_required=4,
        onfi_version="3.0", supports_multiplane=True, supports_cache=True,
    ),
    NANDChipInfo(
        manufacturer="Micron", part_number="MT29F32G08CBACA",
        description="Micron 32Gbit MLC NAND Flash",
        mfr_id=0x2C, dev_id=0x68,
        id_bytes=(0x2C, 0x68, 0x04, 0x46, 0x89),
        page_size=4096, oob_size=224,
        pages_per_block=256, blocks_per_lun=2048,
        luns_per_die=2,
        cell_type=2, ecc_bits_required=4,
        onfi_version="3.0", supports_multiplane=True, supports_cache=True,
    ),

    # ═══════════════════════════════════════════════════════
    #  TOSHIBA / KIOXIA
    # ═══════════════════════════════════════════════════════
    NANDChipInfo(
        manufacturer="Toshiba", part_number="TC58NVG0S3HTA00",
        description="Toshiba 1Gbit SLC NAND Flash",
        mfr_id=0x98, dev_id=0xF1,
        id_bytes=(0x98, 0xF1, 0x80, 0x15, 0x72),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=1024,
        cell_type=1, ecc_bits_required=1,
    ),
    NANDChipInfo(
        manufacturer="Toshiba", part_number="TC58NVG1S3HTA00",
        description="Toshiba 2Gbit SLC NAND Flash",
        mfr_id=0x98, dev_id=0xDA,
        id_bytes=(0x98, 0xDA, 0x90, 0x15, 0x76),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=2048,
        cell_type=1, ecc_bits_required=1,
    ),
    NANDChipInfo(
        manufacturer="Toshiba", part_number="TC58NVG2S0HTA00",
        description="Toshiba 4Gbit SLC NAND Flash",
        mfr_id=0x98, dev_id=0xDC,
        id_bytes=(0x98, 0xDC, 0x90, 0x15, 0x76),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=4096,
        cell_type=1, ecc_bits_required=1,
    ),
    NANDChipInfo(
        manufacturer="Toshiba", part_number="TC58NVG3S0FTA00",
        description="Toshiba 8Gbit MLC NAND Flash",
        mfr_id=0x98, dev_id=0xD3,
        id_bytes=(0x98, 0xD3, 0x91, 0x26, 0x76),
        page_size=4096, oob_size=128,
        pages_per_block=64, blocks_per_lun=4096,
        cell_type=2, ecc_bits_required=4,
        timings=NANDTimings(t_prog=600, t_bers=5000),
    ),
    NANDChipInfo(
        manufacturer="Toshiba", part_number="TC58NVG4T2ETA00",
        description="Toshiba 16Gbit 24nm MLC NAND Flash",
        mfr_id=0x98, dev_id=0xD5,
        id_bytes=(0x98, 0xD5, 0x94, 0x32, 0x76, 0x55),
        page_size=8192, oob_size=232,
        pages_per_block=128, blocks_per_lun=2048,
        cell_type=2, ecc_bits_required=8, ecc_sector_size=512,
    ),
    NANDChipInfo(
        manufacturer="Toshiba", part_number="TC58NVG5T2ETA00",
        description="Toshiba 32Gbit 24nm MLC NAND Flash",
        mfr_id=0x98, dev_id=0xD7,
        id_bytes=(0x98, 0xD7, 0x94, 0x32, 0x76, 0x56),
        page_size=8192, oob_size=232,
        pages_per_block=256, blocks_per_lun=2048,
        cell_type=2, ecc_bits_required=8, ecc_sector_size=512,
    ),

    # ═══════════════════════════════════════════════════════
    #  SK HYNIX
    # ═══════════════════════════════════════════════════════
    NANDChipInfo(
        manufacturer="SK Hynix", part_number="H27U1G8F2BTR",
        description="SK Hynix 1Gbit SLC NAND Flash",
        mfr_id=0xAD, dev_id=0xF1,
        id_bytes=(0xAD, 0xF1, 0x80, 0x1D, 0x44),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=1024,
        cell_type=1, ecc_bits_required=1,
    ),
    NANDChipInfo(
        manufacturer="SK Hynix", part_number="H27U2G8F2CTR",
        description="SK Hynix 2Gbit SLC NAND Flash",
        mfr_id=0xAD, dev_id=0xDA,
        id_bytes=(0xAD, 0xDA, 0x90, 0x95, 0x44),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=2048,
        cell_type=1, ecc_bits_required=1,
    ),
    NANDChipInfo(
        manufacturer="SK Hynix", part_number="H27U4G8F2DTR",
        description="SK Hynix 4Gbit SLC NAND Flash",
        mfr_id=0xAD, dev_id=0xDC,
        id_bytes=(0xAD, 0xDC, 0x11, 0x95, 0x54),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=4096,
        cell_type=1, ecc_bits_required=1,
    ),
    NANDChipInfo(
        manufacturer="SK Hynix", part_number="H27UCG8T2BTR",
        description="SK Hynix 8Gbit MLC NAND Flash",
        mfr_id=0xAD, dev_id=0xD3,
        id_bytes=(0xAD, 0xD3, 0x14, 0x25, 0x64),
        page_size=4096, oob_size=128,
        pages_per_block=128, blocks_per_lun=2048,
        cell_type=2, ecc_bits_required=4,
    ),
    NANDChipInfo(
        manufacturer="SK Hynix", part_number="H27UBG8T2BTR",
        description="SK Hynix 64Gbit MLC NAND Flash",
        mfr_id=0xAD, dev_id=0xDE,
        id_bytes=(0xAD, 0xDE, 0x94, 0xDA, 0x74, 0xC4),
        page_size=8192, oob_size=640,
        pages_per_block=256, blocks_per_lun=2048,
        luns_per_die=2,
        cell_type=2, ecc_bits_required=40, ecc_sector_size=1024,
        onfi_version="3.0", supports_multiplane=True, supports_cache=True,
    ),

    # ═══════════════════════════════════════════════════════
    #  MACRONIX
    # ═══════════════════════════════════════════════════════
    NANDChipInfo(
        manufacturer="Macronix", part_number="MX30LF1G08AA",
        description="Macronix 1Gbit SLC NAND Flash",
        mfr_id=0xC2, dev_id=0xF1,
        id_bytes=(0xC2, 0xF1, 0x80, 0x1D, 0x42),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=1024,
        cell_type=1, ecc_bits_required=4,
        timings=NANDTimings(t_prog=300, t_bers=3000),
    ),
    NANDChipInfo(
        manufacturer="Macronix", part_number="MX30LF2G18AC",
        description="Macronix 2Gbit SLC NAND Flash",
        mfr_id=0xC2, dev_id=0xDA,
        id_bytes=(0xC2, 0xDA, 0x90, 0x95, 0x42),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=2048,
        cell_type=1, ecc_bits_required=4,
    ),
    NANDChipInfo(
        manufacturer="Macronix", part_number="MX60LF8G18AC",
        description="Macronix 8Gbit SLC NAND Flash",
        mfr_id=0xC2, dev_id=0xD3,
        id_bytes=(0xC2, 0xD3, 0xD1, 0x95, 0x58),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=8192,
        cell_type=1, ecc_bits_required=4,
    ),

    # ═══════════════════════════════════════════════════════
    #  NANYA
    # ═══════════════════════════════════════════════════════
    NANDChipInfo(
        manufacturer="Nanya", part_number="NT29F1G08ABAEA",
        description="Nanya 1Gbit SLC NAND Flash",
        mfr_id=0xD3, dev_id=0xF1,
        id_bytes=(0xD3, 0xF1, 0x80, 0x1D, 0x44),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=1024,
        cell_type=1, ecc_bits_required=1,
    ),
    NANDChipInfo(
        manufacturer="Nanya", part_number="NT29F2G08ABAEA",
        description="Nanya 2Gbit SLC NAND Flash",
        mfr_id=0xD3, dev_id=0xDA,
        id_bytes=(0xD3, 0xDA, 0x90, 0x95, 0x44),
        page_size=2048, oob_size=64,
        pages_per_block=64, blocks_per_lun=2048,
        cell_type=1, ecc_bits_required=1,
    ),
]


# ─────────────────────────────────────────────────────────────
#  Lookup Functions
# ─────────────────────────────────────────────────────────────
def lookup_chip(mfr_id: int, dev_id: int,
                id_bytes: Optional[tuple] = None) -> Optional[NANDChipInfo]:
    """
    Look up chip info by manufacturer ID + device ID.
    If id_bytes provided, tries to match full ID sequence first.
    """
    candidates = [c for c in NAND_DATABASE
                  if c.mfr_id == mfr_id and c.dev_id == dev_id]

    if not candidates:
        return None

    # Exact full-ID match first
    if id_bytes and len(id_bytes) >= 5:
        for chip in candidates:
            n = min(len(chip.id_bytes), len(id_bytes))
            if chip.id_bytes[:n] == tuple(id_bytes[:n]):
                return chip

    return candidates[0]


def get_manufacturer_name(mfr_id: int) -> str:
    return MANUFACTURER_IDS.get(mfr_id, f"Unknown (0x{mfr_id:02X})")


def list_chips_by_manufacturer(name: str) -> List[NANDChipInfo]:
    return [c for c in NAND_DATABASE
            if name.lower() in c.manufacturer.lower()]


def get_all_manufacturers() -> List[str]:
    seen = set()
    result = []
    for chip in NAND_DATABASE:
        if chip.manufacturer not in seen:
            seen.add(chip.manufacturer)
            result.append(chip.manufacturer)
    return sorted(result)


def export_database_json() -> str:
    return json.dumps([c.to_dict() for c in NAND_DATABASE], indent=2)


def build_id_lookup() -> Dict[Tuple[int, int], NANDChipInfo]:
    """Build a fast O(1) lookup dict keyed by (mfr_id, dev_id)."""
    return {(c.mfr_id, c.dev_id): c for c in NAND_DATABASE}


# Pre-built fast lookup table
_CHIP_LOOKUP: Dict[Tuple[int, int], NANDChipInfo] = build_id_lookup()


def fast_lookup(mfr_id: int, dev_id: int) -> Optional[NANDChipInfo]:
    return _CHIP_LOOKUP.get((mfr_id, dev_id))
