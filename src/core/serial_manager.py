"""
Serial Communication Manager
==============================
Handles all low-level serial communication with the Teensy 4.1 bridge.

Binary protocol:
  TX (Host → Teensy): [CMD:1][LEN:4][PAYLOAD:LEN][CRC16:2]
  RX (Teensy → Host): [STATUS:1][LEN:4][DATA:LEN][CRC16:2]

CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF)
"""

from __future__ import annotations

import struct
import threading
import time
import logging
from enum import IntEnum
from typing import Optional, Callable, Tuple

import serial
import serial.tools.list_ports

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  Protocol Constants  (must match firmware)
# ─────────────────────────────────────────────────────────────
BAUD_RATE       = 2_000_000
TIMEOUT_DEFAULT = 5.0
TIMEOUT_LONG    = 30.0
MAX_PAYLOAD     = 8192 + 448 + 64   # max page + max OOB + overhead


class Command(IntEnum):
    PING             = 0x01
    GET_FW_VERSION   = 0x02
    NAND_DETECT      = 0x10
    NAND_READ_ID     = 0x11
    NAND_READ_PARAM  = 0x12
    NAND_RESET       = 0x13
    READ_PAGE        = 0x20
    READ_PAGE_OOB    = 0x21
    WRITE_PAGE       = 0x30
    ERASE_BLOCK      = 0x40
    SCAN_BAD_BLOCKS  = 0x50
    GET_STATUS       = 0x60
    SET_POWER        = 0x70
    SET_WP           = 0x71
    BULK_READ        = 0x80
    BULK_WRITE       = 0x81


class StatusCode(IntEnum):
    OK            = 0x00
    ERROR         = 0x01
    BUSY          = 0x02
    TIMEOUT       = 0x03
    BAD_BLOCK     = 0x04
    ECC_ERROR     = 0x05
    WRITE_PROTECT = 0x06
    NAND_FAIL     = 0x07
    CRC_ERROR     = 0x08
    INVALID_CMD   = 0x09


STATUS_MESSAGES = {
    StatusCode.OK:            "OK",
    StatusCode.ERROR:         "General Error",
    StatusCode.BUSY:          "Busy / Progress Update",
    StatusCode.TIMEOUT:       "Timeout",
    StatusCode.BAD_BLOCK:     "Bad Block",
    StatusCode.ECC_ERROR:     "Uncorrectable ECC Error",
    StatusCode.WRITE_PROTECT: "Write Protected",
    StatusCode.NAND_FAIL:     "NAND Operation Failed",
    StatusCode.CRC_ERROR:     "CRC Mismatch",
    StatusCode.INVALID_CMD:   "Invalid Command",
}


class ProtocolError(Exception):
    """Raised when the protocol layer encounters an error."""
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


# ─────────────────────────────────────────────────────────────
#  CRC-16/CCITT-FALSE
# ─────────────────────────────────────────────────────────────
def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
        crc &= 0xFFFF
    return crc


# ─────────────────────────────────────────────────────────────
#  Response Data Class
# ─────────────────────────────────────────────────────────────
class Response:
    __slots__ = ("status", "data")

    def __init__(self, status: int, data: bytes = b""):
        self.status = StatusCode(status) if status in StatusCode._value2member_map_ else status
        self.data   = data

    @property
    def ok(self) -> bool:
        return self.status == StatusCode.OK

    @property
    def busy(self) -> bool:
        return self.status == StatusCode.BUSY

    def __repr__(self):
        return f"Response(status={self.status!r}, data_len={len(self.data)})"


# ─────────────────────────────────────────────────────────────
#  Serial Manager
# ─────────────────────────────────────────────────────────────
class SerialManager:
    """
    Thread-safe serial manager for the Teensy 4.1 NAND Flash bridge.
    
    Usage:
        mgr = SerialManager()
        mgr.connect("COM5")
        response = mgr.send_command(Command.PING)
    """

    def __init__(self):
        self._port:  Optional[serial.Serial] = None
        self._lock   = threading.RLock()
        self._connected = False
        self._port_name = ""
        
        # Statistics
        self.bytes_sent     = 0
        self.bytes_received = 0
        self.error_count    = 0
        self.cmd_count      = 0

    # ── Connection Management ─────────────────────────────────
    def connect(self, port: str, baud: int = BAUD_RATE) -> bool:
        with self._lock:
            if self._connected:
                self.disconnect()
            try:
                self._port = serial.Serial(
                    port       = port,
                    baudrate   = baud,
                    bytesize   = serial.EIGHTBITS,
                    parity     = serial.PARITY_NONE,
                    stopbits   = serial.STOPBITS_ONE,
                    timeout    = TIMEOUT_DEFAULT,
                    write_timeout = 5.0,
                    xonxoff    = False,
                    rtscts     = False,
                    dsrdtr     = False,
                )
                self._port.reset_input_buffer()
                self._port.reset_output_buffer()
                self._connected = True
                self._port_name = port
                logger.info("Connected to %s @ %d baud", port, baud)
                return True
            except serial.SerialException as e:
                logger.error("Failed to connect to %s: %s", port, e)
                self._port = None
                self._connected = False
                return False

    def disconnect(self):
        with self._lock:
            if self._port and self._port.is_open:
                self._port.close()
            self._port = None
            self._connected = False
            logger.info("Disconnected from serial port")

    @property
    def connected(self) -> bool:
        return self._connected and self._port is not None and self._port.is_open

    @property
    def port_name(self) -> str:
        return self._port_name

    # ── Port Discovery ────────────────────────────────────────
    @staticmethod
    def list_ports() -> list[dict]:
        """Return available serial ports with device description."""
        ports = []
        for p in serial.tools.list_ports.comports():
            ports.append({
                "port":        p.device,
                "description": p.description or "",
                "hwid":        p.hwid or "",
                "manufacturer": p.manufacturer or "",
                "vid":         p.vid,
                "pid":         p.pid,
                "is_teensy":   (p.vid == 0x16C0),   # PJRC Vendor ID
            })
        return sorted(ports, key=lambda x: x["port"])

    @staticmethod
    def find_teensy_port() -> Optional[str]:
        """Auto-detect first Teensy 4.1 USB serial port."""
        for p in serial.tools.list_ports.comports():
            if p.vid == 0x16C0:  # PJRC VID
                return p.device
        # Fallback: look for common descriptions
        for p in serial.tools.list_ports.comports():
            desc = (p.description or "").lower()
            if "teensy" in desc or "usb serial" in desc:
                return p.device
        return None

    # ── Low-level I/O ─────────────────────────────────────────
    def _write_raw(self, data: bytes):
        if not self.connected:
            raise ProtocolError("Not connected")
        try:
            n = self._port.write(data)
            self.bytes_sent += n
        except serial.SerialTimeoutException:
            raise ProtocolError("Write timeout")
        except serial.SerialException as e:
            self._connected = False
            raise ProtocolError(f"Write error: {e}")

    def _read_exact(self, n: int, timeout: float = TIMEOUT_DEFAULT) -> bytes:
        if not self.connected:
            raise ProtocolError("Not connected")
        self._port.timeout = timeout
        data = self._port.read(n)
        if len(data) != n:
            raise ProtocolError(
                f"Read timeout: expected {n} bytes, got {len(data)}"
            )
        self.bytes_received += len(data)
        return data

    # ── Packet Assembly ───────────────────────────────────────
    def _build_packet(self, cmd: int, payload: bytes = b"") -> bytes:
        """Build a command packet: [CMD:1][LEN:4][PAYLOAD][CRC16:2]"""
        hdr = bytes([cmd]) + struct.pack("<I", len(payload))
        body = hdr + payload
        checksum = crc16(body)
        return body + struct.pack("<H", checksum)

    def _parse_response(self, timeout: float = TIMEOUT_DEFAULT) -> Response:
        """Read and validate a response packet from the Teensy."""
        # Header: STATUS(1) + LEN(4)
        hdr = self._read_exact(5, timeout)
        status = hdr[0]
        data_len = struct.unpack("<I", hdr[1:5])[0]

        if data_len > MAX_PAYLOAD:
            raise ProtocolError(f"Response data_len too large: {data_len}")

        data = b""
        if data_len > 0:
            data = self._read_exact(data_len, timeout)

        # CRC
        crc_bytes = self._read_exact(2, timeout)
        recv_crc  = struct.unpack("<H", crc_bytes)[0]
        calc_crc  = crc16(hdr + data)

        if recv_crc != calc_crc:
            raise ProtocolError(
                f"CRC mismatch: expected 0x{calc_crc:04X}, got 0x{recv_crc:04X}"
            )

        return Response(status, data)

    # ── Command Interface ─────────────────────────────────────
    def send_command(self,
                     cmd: int,
                     payload: bytes = b"",
                     timeout: float = TIMEOUT_DEFAULT,
                     progress_cb: Optional[Callable[[Response], None]] = None
                     ) -> Response:
        """
        Send a command and return the final response.
        
        Handles BUSY (progress) responses if progress_cb is provided.
        """
        with self._lock:
            if not self.connected:
                raise ProtocolError("Not connected")

            packet = self._build_packet(cmd, payload)
            logger.debug("TX cmd=0x%02X payload_len=%d", cmd, len(payload))

            self._write_raw(packet)
            self.cmd_count += 1

            while True:
                resp = self._parse_response(timeout)
                logger.debug("RX status=%s data_len=%d", resp.status, len(resp.data))

                if resp.busy and progress_cb:
                    progress_cb(resp)
                    continue
                
                return resp

    # ── High-level Commands ───────────────────────────────────
    def ping(self) -> bool:
        try:
            resp = self.send_command(Command.PING, timeout=3.0)
            return resp.ok and resp.data == b"PONG"
        except ProtocolError:
            return False

    def get_firmware_version(self) -> Optional[str]:
        try:
            resp = self.send_command(Command.GET_FW_VERSION, timeout=3.0)
            if resp.ok and len(resp.data) >= 3:
                return f"{resp.data[0]}.{resp.data[1]}.{resp.data[2]}"
        except ProtocolError as e:
            logger.error("get_firmware_version: %s", e)
        return None

    def nand_reset(self) -> bool:
        try:
            resp = self.send_command(Command.NAND_RESET, timeout=10.0)
            return resp.ok
        except ProtocolError as e:
            logger.error("nand_reset: %s", e)
            return False

    def nand_detect(self) -> Optional[dict]:
        """Detect NAND chip and return raw geometry dict."""
        try:
            resp = self.send_command(Command.NAND_DETECT, timeout=15.0)
            if not resp.ok:
                return None
            return self._parse_detect_response(resp.data)
        except ProtocolError as e:
            logger.error("nand_detect: %s", e)
            return None

    def _parse_detect_response(self, data: bytes) -> dict:
        """Parse binary detect response into geometry dict."""
        if len(data) < 50:
            raise ProtocolError("Detect response too short")

        pos = 0
        mfr_id  = data[pos]; pos += 1
        dev_id  = data[pos]; pos += 1
        id_bytes = bytes(data[pos:pos+8]); pos += 8
        page_size  = struct.unpack_from("<H", data, pos)[0]; pos += 2
        oob_size   = struct.unpack_from("<H", data, pos)[0]; pos += 2
        ppb        = struct.unpack_from("<I", data, pos)[0]; pos += 4
        bpl        = struct.unpack_from("<I", data, pos)[0]; pos += 4
        luns       = data[pos]; pos += 1
        bpc        = data[pos]; pos += 1
        col_cyc    = data[pos]; pos += 1
        row_cyc    = data[pos]; pos += 1
        onfi       = data[pos]; pos += 1
        onfi_mfr   = data[pos:pos+13].decode("ascii", errors="replace").rstrip("\x00"); pos += 13
        onfi_model = data[pos:pos+21].decode("ascii", errors="replace").rstrip("\x00"); pos += 21

        return {
            "mfr_id":          mfr_id,
            "dev_id":          dev_id,
            "id_bytes":        id_bytes,
            "page_size":       page_size,
            "oob_size":        oob_size,
            "pages_per_block": ppb,
            "blocks_per_lun":  bpl,
            "luns":            luns,
            "bits_per_cell":   bpc,
            "col_addr_cycles": col_cyc,
            "row_addr_cycles": row_cyc,
            "onfi_compliant":  bool(onfi),
            "onfi_mfr":        onfi_mfr,
            "onfi_model":      onfi_model,
        }

    def read_page(self, page_num: int, read_oob: bool = True,
                  timeout: float = TIMEOUT_DEFAULT) -> Optional[bytes]:
        """Read a single NAND page (data + optional OOB)."""
        payload = struct.pack("<IB", page_num, 1 if read_oob else 0)
        try:
            resp = self.send_command(Command.READ_PAGE, payload, timeout)
            return resp.data if resp.ok else None
        except ProtocolError as e:
            logger.error("read_page(%d): %s", page_num, e)
            return None

    def write_page(self, page_num: int, data: bytes,
                   timeout: float = TIMEOUT_DEFAULT) -> bool:
        payload = struct.pack("<I", page_num) + data
        try:
            resp = self.send_command(Command.WRITE_PAGE, payload, timeout)
            return resp.ok
        except ProtocolError as e:
            logger.error("write_page(%d): %s", page_num, e)
            return False

    def erase_block(self, block_num: int,
                    timeout: float = TIMEOUT_LONG) -> bool:
        payload = struct.pack("<I", block_num)
        try:
            resp = self.send_command(Command.ERASE_BLOCK, payload, timeout)
            return resp.ok
        except ProtocolError as e:
            logger.error("erase_block(%d): %s", block_num, e)
            return False

    def scan_bad_blocks(self,
                        progress_cb: Optional[Callable[[int, int, int], None]] = None
                        ) -> Optional[list[int]]:
        """
        Scan all blocks for bad blocks.
        progress_cb(current_block, total_blocks, bad_count)
        Returns list of bad block numbers.
        """
        bad_blocks = []

        def on_busy(resp: Response):
            if len(resp.data) >= 8 and resp.data[0] == 0xBB:
                cur   = struct.unpack_from("<I", resp.data, 1)[0]
                total = struct.unpack_from("<I", resp.data, 4)[0]
                bad   = resp.data[7]
                if progress_cb:
                    progress_cb(cur, total, bad)

        try:
            resp = self.send_command(
                Command.SCAN_BAD_BLOCKS, b"",
                timeout=120.0,
                progress_cb=on_busy
            )
            if not resp.ok:
                return None
            if len(resp.data) < 4:
                return []
            bad_count = struct.unpack_from("<I", resp.data, 0)[0]
            for i in range(bad_count):
                off = 4 + i * 4
                if off + 4 <= len(resp.data):
                    blk = struct.unpack_from("<I", resp.data, off)[0]
                    bad_blocks.append(blk)
            return bad_blocks
        except ProtocolError as e:
            logger.error("scan_bad_blocks: %s", e)
            return None

    def set_power(self, enable: bool) -> bool:
        try:
            resp = self.send_command(Command.SET_POWER, bytes([1 if enable else 0]))
            return resp.ok
        except ProtocolError:
            return False

    def set_write_protect(self, protect: bool) -> bool:
        try:
            resp = self.send_command(Command.SET_WP, bytes([1 if protect else 0]))
            return resp.ok
        except ProtocolError:
            return False

    def get_hardware_status(self) -> Optional[dict]:
        try:
            resp = self.send_command(Command.GET_STATUS, timeout=3.0)
            if resp.ok and len(resp.data) >= 4:
                return {
                    "nand_status":     resp.data[0],
                    "ready":           bool(resp.data[1]),
                    "write_protected": bool(resp.data[2]),
                    "powered":         bool(resp.data[3]),
                }
        except ProtocolError as e:
            logger.error("get_hardware_status: %s", e)
        return None

    # ── Stats ────────────────────────────────────────────────
    def get_stats(self) -> dict:
        return {
            "bytes_sent":     self.bytes_sent,
            "bytes_received": self.bytes_received,
            "error_count":    self.error_count,
            "cmd_count":      self.cmd_count,
            "port":           self._port_name,
            "connected":      self.connected,
        }

    def reset_stats(self):
        self.bytes_sent = 0
        self.bytes_received = 0
        self.error_count = 0
        self.cmd_count = 0
