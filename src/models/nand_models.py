"""
NAND Operation Models
=====================
Data classes for representing NAND Flash operations,
results, sessions, and bad block maps.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Dict, Any
import time
import uuid


# ─────────────────────────────────────────────────────────────
#  Enums
# ─────────────────────────────────────────────────────────────
class OperationType(Enum):
    READ_PAGE       = "Read Page"
    WRITE_PAGE      = "Write Page"
    ERASE_BLOCK     = "Erase Block"
    SCAN_BAD_BLOCKS = "Scan Bad Blocks"
    READ_FULL_DUMP  = "Full Read Dump"
    WRITE_FULL_DUMP = "Full Write (Program)"
    CLONE           = "Clone (Read+Write)"
    DETECT          = "Detect/Identify"
    VERIFY          = "Verify"
    ERASE_ALL       = "Chip Erase"


class OperationStatus(Enum):
    IDLE        = "Idle"
    RUNNING     = "Running"
    PAUSED      = "Paused"
    COMPLETED   = "Completed"
    FAILED      = "Failed"
    CANCELLED   = "Cancelled"
    VERIFYING   = "Verifying"


class ConnectionStatus(Enum):
    DISCONNECTED = "Disconnected"
    CONNECTING   = "Connecting"
    CONNECTED    = "Connected"
    ERROR        = "Error"


class PageStatus(Enum):
    UNKNOWN = 0
    CLEAN   = 1   # All 0xFF
    DATA    = 2   # Contains data
    BAD     = 3   # Bad page/block
    ECC_ERR = 4   # Uncorrectable ECC error
    ERASED  = 5   # Confirmed erased


# ─────────────────────────────────────────────────────────────
#  Device Info
# ─────────────────────────────────────────────────────────────
@dataclass
class DeviceInfo:
    """Live device information from hardware detection."""
    connected:       bool   = False
    port:            str    = ""
    firmware_ver:    str    = "Unknown"
    
    # NAND info
    mfr_id:          int    = 0
    dev_id:          int    = 0
    id_bytes:        bytes  = b""
    manufacturer:    str    = "Unknown"
    model:           str    = "Unknown"
    
    # Geometry
    page_size:       int    = 0
    oob_size:        int    = 0
    pages_per_block: int    = 0
    blocks_per_lun:  int    = 0
    luns:            int    = 1
    col_addr_cycles: int    = 2
    row_addr_cycles: int    = 3
    
    # Status
    write_protected: bool   = False
    power_on:        bool   = False
    onfi_compliant:  bool   = False
    onfi_mfr:        str    = ""
    onfi_model:      str    = ""
    
    @property
    def total_pages(self) -> int:
        return self.pages_per_block * self.blocks_per_lun * self.luns

    @property
    def total_blocks(self) -> int:
        return self.blocks_per_lun * self.luns

    @property
    def total_size_bytes(self) -> int:
        return self.total_pages * self.page_size

    @property
    def total_size_mb(self) -> float:
        return self.total_size_bytes / (1024 * 1024)

    @property
    def total_size_gb(self) -> float:
        return self.total_size_bytes / (1024 ** 3)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manufacturer":    self.manufacturer,
            "model":           self.model,
            "mfr_id":          f"0x{self.mfr_id:02X}",
            "dev_id":          f"0x{self.dev_id:02X}",
            "id_bytes":        " ".join(f"0x{b:02X}" for b in self.id_bytes),
            "page_size":       f"{self.page_size} B",
            "oob_size":        f"{self.oob_size} B",
            "pages_per_block": self.pages_per_block,
            "blocks_per_lun":  self.blocks_per_lun,
            "luns":            self.luns,
            "total_pages":     self.total_pages,
            "total_blocks":    self.total_blocks,
            "size_mb":         f"{self.total_size_mb:.1f} MB",
            "onfi":            "Yes" if self.onfi_compliant else "No",
            "write_protected": "Yes" if self.write_protected else "No",
        }


# ─────────────────────────────────────────────────────────────
#  Operation Progress
# ─────────────────────────────────────────────────────────────
@dataclass
class OperationProgress:
    """Tracks progress of a long-running NAND operation."""
    operation_id:    str   = field(default_factory=lambda: str(uuid.uuid4())[:8])
    op_type:         OperationType = OperationType.READ_FULL_DUMP
    status:          OperationStatus = OperationStatus.IDLE

    # Progress
    current:         int   = 0   # pages or blocks processed
    total:           int   = 0
    bytes_processed: int   = 0
    bytes_total:     int   = 0

    # Timing
    start_time:      float = 0.0
    end_time:        float = 0.0

    # Results
    bad_blocks:      List[int] = field(default_factory=list)
    ecc_errors:      int  = 0
    ecc_corrected:   int  = 0
    errors:          List[str] = field(default_factory=list)
    warnings:        List[str] = field(default_factory=list)

    # Rate tracking (ring buffer for smoothing)
    _rate_samples:   List[float] = field(default_factory=list, repr=False)
    _last_sample_t:  float = field(default=0.0, repr=False)

    @property
    def percent(self) -> float:
        if self.total == 0:
            return 0.0
        return min(100.0, (self.current / self.total) * 100.0)

    @property
    def elapsed_seconds(self) -> float:
        if self.start_time == 0:
            return 0.0
        end = self.end_time if self.end_time > 0 else time.monotonic()
        return end - self.start_time

    @property
    def throughput_kbps(self) -> float:
        """Bytes per second in KB/s."""
        elapsed = self.elapsed_seconds
        if elapsed < 0.001:
            return 0.0
        return (self.bytes_processed / elapsed) / 1024.0

    @property
    def eta_seconds(self) -> float:
        """Estimated time remaining in seconds."""
        if self.percent <= 0 or self.elapsed_seconds < 0.5:
            return 0.0
        total_est = self.elapsed_seconds / (self.percent / 100.0)
        return max(0.0, total_est - self.elapsed_seconds)

    def start(self):
        self.start_time = time.monotonic()
        self.status = OperationStatus.RUNNING

    def complete(self):
        self.end_time = time.monotonic()
        self.status = OperationStatus.COMPLETED
        self.current = self.total

    def fail(self, reason: str = ""):
        self.end_time = time.monotonic()
        self.status = OperationStatus.FAILED
        if reason:
            self.errors.append(reason)

    def cancel(self):
        self.end_time = time.monotonic()
        self.status = OperationStatus.CANCELLED


# ─────────────────────────────────────────────────────────────
#  Bad Block Map
# ─────────────────────────────────────────────────────────────
@dataclass
class BadBlockMap:
    """Tracks bad blocks for a NAND device."""
    total_blocks:    int  = 0
    bad_blocks:      List[int] = field(default_factory=list)
    factory_bad:     List[int] = field(default_factory=list)  # Factory-marked bad
    grown_bad:       List[int] = field(default_factory=list)  # Grown bad blocks

    @property
    def bad_count(self) -> int:
        return len(self.bad_blocks)

    @property
    def good_count(self) -> int:
        return max(0, self.total_blocks - self.bad_count)

    @property
    def bad_percentage(self) -> float:
        if self.total_blocks == 0:
            return 0.0
        return (self.bad_count / self.total_blocks) * 100.0

    def is_bad(self, block: int) -> bool:
        return block in self.bad_blocks

    def mark_bad(self, block: int, factory: bool = False):
        if block not in self.bad_blocks:
            self.bad_blocks.append(block)
            if factory:
                self.factory_bad.append(block)
            else:
                self.grown_bad.append(block)

    def to_bitmap(self) -> bytearray:
        """Return a compact bitmap: 1 bit per block (1=bad)."""
        n = (self.total_blocks + 7) // 8
        bm = bytearray(n)
        for blk in self.bad_blocks:
            if 0 <= blk < self.total_blocks:
                bm[blk // 8] |= (1 << (blk % 8))
        return bm


# ─────────────────────────────────────────────────────────────
#  Session
# ─────────────────────────────────────────────────────────────
@dataclass
class NANDSession:
    """A complete NAND Flash programming session."""
    session_id:      str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at:      float = field(default_factory=time.time)
    
    device:          DeviceInfo = field(default_factory=DeviceInfo)
    bad_block_map:   BadBlockMap = field(default_factory=BadBlockMap)
    operations:      List[OperationProgress] = field(default_factory=list)
    
    # File paths
    source_file:     Optional[str] = None
    output_file:     Optional[str] = None
    
    # Options
    use_ecc:         bool = True
    skip_bad_blocks: bool = True
    verify_after_write: bool = True
    include_oob:     bool = False

    def add_operation(self, op: OperationProgress):
        self.operations.append(op)

    @property
    def last_operation(self) -> Optional[OperationProgress]:
        return self.operations[-1] if self.operations else None
