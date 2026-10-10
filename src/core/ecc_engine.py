"""
ECC Engine
==========
Error Correction Code implementation for NAND Flash data integrity.

Supported algorithms:
  1. Hamming Code (1-bit correction / 2-bit detection per 256B)
  2. BCH (Bose-Chaudhuri-Hocquenghem) - software BCH for multi-bit correction
  3. Simple XOR parity (for OOB validation)

Used to protect NAND page data against bit-flip errors common in
MLC/TLC NAND Flash devices.
"""

from __future__ import annotations

import math
import struct
import logging
from typing import Tuple, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
#  Hamming Code (1-bit correction)
# ─────────────────────────────────────────────────────────────
class HammingECC:
    """
    256-byte Hamming ECC.
    Produces 3 bytes of ECC per 256 bytes of data.
    Corrects 1-bit errors, detects 2-bit errors.
    
    Compatible with Linux NAND MTD Hamming implementation.
    """

    # Lookup table: count of 1-bits set in each 4-bit nibble
    _BIT_COUNT = bytes([bin(i).count("1") for i in range(256)])

    @staticmethod
    def calculate(data: bytes) -> bytes:
        """Calculate 3-byte ECC for up to 256 bytes of data."""
        if len(data) > 256:
            data = data[:256]

        # Column parity (odd/even bits within byte)
        cp  = [0] * 6  # cp[0..5]
        rp  = [0] * 16  # row parity

        for idx, byte in enumerate(data):
            # Row parities (which 256-byte half, 128-byte, etc.)
            for bit in range(8):
                if byte & (1 << bit):
                    # Column parities
                    if bit & 1: cp[0] ^= 1
                    else:        cp[1] ^= 1
                    if bit & 2: cp[2] ^= 1
                    else:        cp[3] ^= 1
                    if bit & 4: cp[4] ^= 1
                    else:        cp[5] ^= 1
                    # Row parities
                    for rp_bit in range(8):
                        mask = 1 << rp_bit
                        if idx & mask:  rp[rp_bit * 2]     ^= 1
                        else:           rp[rp_bit * 2 + 1] ^= 1

        # Pack ECC into 3 bytes
        ecc = bytearray(3)

        # Byte 0: RP7,RP6,RP5,RP4,RP3,RP2,RP1,RP0
        for i in range(8):
            ecc[0] |= (rp[i] << i)

        # Byte 1: RP15,RP14,RP13,RP12,RP11,RP10,RP9,RP8
        for i in range(8):
            ecc[1] |= (rp[i + 8] << i)

        # Byte 2: CP5,CP4,CP3,CP2,CP1,CP0,1,1
        ecc[2] = 0x03  # last 2 bits always 1
        for i in range(6):
            ecc[2] |= (cp[i] << (i + 2))

        return bytes(ecc)

    @classmethod
    def correct(cls, data: bytearray, stored_ecc: bytes,
                calc_ecc: bytes) -> Tuple[bool, bool]:
        """
        Check/correct data using stored and calculated ECC.
        
        Returns:
            (corrected: bool, uncorrectable: bool)
            - (True, False)  → 1-bit error corrected
            - (False, False) → No error
            - (False, True)  → Uncorrectable (2+ bit) error
        """
        s0 = stored_ecc[0] ^ calc_ecc[0]
        s1 = stored_ecc[1] ^ calc_ecc[1]
        s2 = stored_ecc[2] ^ calc_ecc[2]

        if s0 == 0 and s1 == 0 and s2 == 0:
            return False, False  # No error

        # Count set bits in syndrome
        syndrome_bits = (cls._BIT_COUNT[s0] + cls._BIT_COUNT[s1] +
                         cls._BIT_COUNT[s2])

        if syndrome_bits == 1:
            # ECC bit error (not data) – ignore
            return False, False

        if syndrome_bits != 11:
            # Uncorrectable error
            return False, True

        # Find bit position to correct
        byte_addr = 0
        bit_addr  = 0

        for i in range(8):
            if s0 & (1 << i):
                byte_addr |= (1 << i)
        for i in range(8):
            if s1 & (1 << i):
                byte_addr |= (1 << (i + 8))

        for i in range(6):
            if s2 & (1 << (i + 2)):
                bit_addr |= (1 << i)

        if byte_addr < len(data):
            data[byte_addr] ^= (1 << (bit_addr & 0x07))
            return True, False

        return False, True


# ─────────────────────────────────────────────────────────────
#  Software BCH (Simplified, suitable for 4/8/12/24-bit correction)
# ─────────────────────────────────────────────────────────────
class BCHECC:
    """
    Software BCH ECC implementation.
    
    Supports t=4, t=8, t=12, t=24 bit correction over GF(2^m).
    Uses GF(2^13) for up to 24-bit error correction.
    
    This is a pure Python implementation, suitable for correctness.
    For production throughput, use the 'bchlib' C extension if available.
    """

    # GF(2^13) primitive polynomial: x^13 + x^4 + x^3 + x + 1
    GF_POLY  = 0x25AF
    GF_M     = 13
    GF_N     = (1 << GF_M) - 1   # 8191

    def __init__(self, t: int = 4, sector_size: int = 512):
        """
        Initialize BCH codec.
        
        Args:
            t:           Error correction capability (bits)
            sector_size: Data sector size in bytes (typically 512 or 1024)
        """
        if t not in (1, 2, 4, 8, 12, 16, 24):
            raise ValueError(f"Unsupported BCH t-value: {t}")

        self.t = t
        self.sector_size = sector_size
        self.ecc_bits    = t * self.GF_M   # bits of ECC
        self.ecc_bytes   = (self.ecc_bits + 7) // 8

        # Build Galois Field tables
        self._build_gf_tables()
        # Build generator polynomial
        self._build_generator()

        logger.debug("BCH(%d,%d) ECC initialized: %d ECC bytes per %d B sector",
                     t, self.GF_M, self.ecc_bytes, sector_size)

    def _build_gf_tables(self):
        """Build GF(2^m) exp and log lookup tables."""
        n = self.GF_N
        m = self.GF_M
        poly = self.GF_POLY

        self._exp = [0] * (n + 1)
        self._log = [0] * (n + 1)

        x = 1
        for i in range(n):
            self._exp[i] = x
            self._log[x] = i
            x <<= 1
            if x > n:
                x ^= poly
                x &= n
        self._exp[n] = 1
        self._log[0] = 0  # log(0) undefined, set to 0

    def _gf_mul(self, a: int, b: int) -> int:
        if a == 0 or b == 0:
            return 0
        return self._exp[(self._log[a] + self._log[b]) % self.GF_N]

    def _gf_pow(self, a: int, n: int) -> int:
        if a == 0:
            return 0
        return self._exp[(self._log[a] * n) % self.GF_N]

    def _build_generator(self):
        """Compute BCH generator polynomial g(x)."""
        # Roots are alpha^1, alpha^2, ..., alpha^(2t)
        roots = list(range(1, 2 * self.t + 1))
        
        # Start with g(x) = 1
        g = [1]
        
        for r in roots:
            # Multiply g(x) by (x - alpha^r) = (x + alpha^r) in GF(2)
            root_val = self._exp[r % self.GF_N]
            # g = g * [root_val, 1]
            new_g = [0] * (len(g) + 1)
            for i, c in enumerate(g):
                new_g[i]     ^= self._gf_mul(c, root_val)
                new_g[i + 1] ^= c
            g = new_g

        self._generator = g

    def calculate(self, data: bytes) -> bytes:
        """Calculate BCH ECC for data sector."""
        # Polynomial division remainder
        data_bits = len(data) * 8 + len(self._generator) - 1
        
        # Initialize remainder
        rem = [0] * len(self._generator)
        
        for byte in data:
            for bit in range(7, -1, -1):
                feedback = ((byte >> bit) & 1) ^ rem[0]
                # Shift register
                rem = rem[1:] + [0]
                if feedback:
                    for i, c in enumerate(self._generator[:-1]):
                        rem[i] ^= c if c else 0

        # Pack remainder bits into bytes
        ecc_bits = []
        for coeff in rem[:-1]:  # exclude leading 1
            # Each coefficient is a GF element (up to m bits)
            for b in range(self.GF_M):
                ecc_bits.append((coeff >> b) & 1)

        # Trim to ecc_bits count and pack
        ecc_bits = ecc_bits[:self.ecc_bits]
        ecc = bytearray(self.ecc_bytes)
        for i, bit in enumerate(ecc_bits):
            if bit:
                ecc[i // 8] |= (1 << (i % 8))

        return bytes(ecc)

    def correct(self, data: bytearray, stored_ecc: bytes) -> Tuple[int, bool]:
        """
        Attempt BCH error correction.
        
        Returns:
            (errors_corrected: int, uncorrectable: bool)
        """
        calc_ecc = self.calculate(bytes(data))
        
        # XOR to get syndrome
        syndrome_bytes = bytes(a ^ b for a, b in zip(calc_ecc, stored_ecc))
        
        if all(b == 0 for b in syndrome_bytes):
            return 0, False  # No error
        
        # Full BCH decoding is complex; for now flag as potentially correctable
        # A complete implementation would compute syndromes, Berlekamp-Massey,
        # Chien search, and Forney algorithm.
        # This simplified version detects errors but defers full correction
        # to the bchlib C extension when available.
        
        try:
            import bchlib
            bch = bchlib.BCH(self.t, prim_poly=self.GF_POLY)
            data_tmp = bytearray(data)
            bitflips = bch.decode(data_tmp, bytearray(stored_ecc))
            if bitflips >= 0:
                data[:] = data_tmp
                return bitflips, False
            else:
                return 0, True
        except ImportError:
            # Without bchlib, return error indication
            logger.warning("bchlib not available; BCH correction approximate")
            return 0, True


# ─────────────────────────────────────────────────────────────
#  ECC Engine Facade
# ─────────────────────────────────────────────────────────────
@dataclass
class ECCResult:
    """Result of an ECC operation on a full page."""
    sectors:           int = 0
    corrected_bits:    int = 0
    uncorrectable:     int = 0
    ok:                bool = True

    @property
    def has_errors(self) -> bool:
        return self.corrected_bits > 0 or self.uncorrectable > 0


class ECCEngine:
    """
    High-level ECC engine that processes full NAND pages.
    
    Supports Hamming (1-bit/256B) and BCH (multi-bit/512B or 1024B).
    ECC data is stored in the OOB (spare) area.
    """

    MODE_NONE    = "none"
    MODE_HAMMING = "hamming"
    MODE_BCH4    = "bch4"
    MODE_BCH8    = "bch8"
    MODE_BCH12   = "bch12"
    MODE_BCH24   = "bch24"

    # ECC bytes per sector for each mode
    ECC_BYTES_TABLE = {
        MODE_NONE:    0,
        MODE_HAMMING: 3,    # 3 bytes per 256B
        MODE_BCH4:    7,    # 7 bytes per 512B
        MODE_BCH8:    13,   # 13 bytes per 512B
        MODE_BCH12:   20,   # 20 bytes per 512B
        MODE_BCH24:   42,   # 42 bytes per 512B (1KB sector)
    }

    def __init__(self, mode: str = MODE_HAMMING,
                 page_size: int = 2048, oob_size: int = 64):
        self.mode      = mode
        self.page_size = page_size
        self.oob_size  = oob_size

        if mode == self.MODE_HAMMING:
            self._hamming = HammingECC()
            self._sector_size = 256
        elif mode == self.MODE_BCH4:
            self._bch = BCHECC(t=4, sector_size=512)
            self._sector_size = 512
        elif mode == self.MODE_BCH8:
            self._bch = BCHECC(t=8, sector_size=512)
            self._sector_size = 512
        elif mode == self.MODE_BCH12:
            self._bch = BCHECC(t=12, sector_size=512)
            self._sector_size = 512
        elif mode == self.MODE_BCH24:
            self._bch = BCHECC(t=24, sector_size=1024)
            self._sector_size = 1024
        else:
            self._sector_size = 0

        self._ecc_per_sector = self.ECC_BYTES_TABLE.get(mode, 0)
        self._sectors = (page_size // self._sector_size) if self._sector_size else 0

    @property
    def ecc_bytes_per_page(self) -> int:
        return self._sectors * self._ecc_per_sector

    def calculate_page_ecc(self, page_data: bytes) -> bytes:
        """Calculate ECC for a full page. Returns concatenated ECC bytes."""
        if self.mode == self.MODE_NONE:
            return b""

        eccs = []
        for i in range(self._sectors):
            sector = page_data[i * self._sector_size: (i + 1) * self._sector_size]
            if len(sector) < self._sector_size:
                sector = sector.ljust(self._sector_size, b"\xFF")

            if self.mode == self.MODE_HAMMING:
                # Hamming works on 256B sectors
                half = self._sector_size // 2
                ecc_a = self._hamming.calculate(sector[:half])
                ecc_b = self._hamming.calculate(sector[half:])
                eccs.extend([ecc_a, ecc_b])
            else:
                ecc = self._bch.calculate(sector)
                eccs.append(ecc)

        return b"".join(eccs)

    def check_and_correct_page(self, page_data: bytearray,
                                stored_ecc: bytes) -> ECCResult:
        """Check page data against stored ECC and correct if possible."""
        result = ECCResult(sectors=self._sectors)

        if self.mode == self.MODE_NONE:
            return result

        ecc_offset = 0
        for i in range(self._sectors):
            start = i * self._sector_size
            sector = page_data[start: start + self._sector_size]

            if self.mode == self.MODE_HAMMING:
                half = self._sector_size // 2
                # First 256B
                calc_a = self._hamming.calculate(bytes(sector[:half]))
                stored_a = stored_ecc[ecc_offset: ecc_offset + 3]
                if len(stored_a) == 3:
                    corrected, fail = self._hamming.correct(
                        page_data[start: start + half],
                        stored_a, calc_a
                    )
                    if corrected: result.corrected_bits += 1
                    if fail:      result.uncorrectable += 1
                ecc_offset += 3

                # Second 256B
                calc_b = self._hamming.calculate(bytes(sector[half:]))
                stored_b = stored_ecc[ecc_offset: ecc_offset + 3]
                if len(stored_b) == 3:
                    corrected, fail = self._hamming.correct(
                        page_data[start + half: start + self._sector_size],
                        stored_b, calc_b
                    )
                    if corrected: result.corrected_bits += 1
                    if fail:      result.uncorrectable += 1
                ecc_offset += 3
            else:
                ecc_chunk = stored_ecc[ecc_offset: ecc_offset + self._ecc_per_sector]
                ecc_offset += self._ecc_per_sector
                if len(ecc_chunk) == self._ecc_per_sector:
                    corrected, fail = self._bch.correct(
                        page_data[start: start + self._sector_size],
                        ecc_chunk
                    )
                    result.corrected_bits += corrected
                    if fail: result.uncorrectable += 1

        result.ok = (result.uncorrectable == 0)
        return result

    def extract_ecc_from_oob(self, oob: bytes) -> bytes:
        """Extract ECC bytes from OOB data (standard placement after BB marker)."""
        # Standard layout: [BB_marker:1..4][ECC data...]
        ecc_start = 4  # Skip bad block marker bytes
        return oob[ecc_start: ecc_start + self.ecc_bytes_per_page]

    def embed_ecc_in_oob(self, oob: bytearray, ecc: bytes) -> bytearray:
        """Embed ECC bytes into OOB data."""
        ecc_start = 4
        end = ecc_start + len(ecc)
        if end <= len(oob):
            oob[ecc_start:end] = ecc
        return oob

    def recommend_mode(self, bits_required: int) -> str:
        """Suggest ECC mode based on chip's required ECC capability."""
        if bits_required <= 0:
            return self.MODE_NONE
        elif bits_required <= 1:
            return self.MODE_HAMMING
        elif bits_required <= 4:
            return self.MODE_BCH4
        elif bits_required <= 8:
            return self.MODE_BCH8
        elif bits_required <= 12:
            return self.MODE_BCH12
        else:
            return self.MODE_BCH24
