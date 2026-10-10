"""
NAND Operations Engine
======================
High-level NAND Flash operations: read, write, erase, clone, verify.
Orchestrates the SerialManager and ECCEngine with progress reporting.

All blocking operations run in a background thread and emit signals
via PyQt6 to keep the GUI responsive.
"""

from __future__ import annotations

import io
import os
import logging
import threading
import time
from typing import Optional, Callable, List

from PyQt6.QtCore import QObject, pyqtSignal, QThread

from .serial_manager import SerialManager, ProtocolError
from .ecc_engine     import ECCEngine
from ..models.nand_models import (
    DeviceInfo, OperationProgress, OperationType, OperationStatus,
    BadBlockMap, NANDSession
)
from ..models.chip_database import lookup_chip, get_manufacturer_name, fast_lookup
from ..utils.file_formats import (
    NANDImageWriter, NANDImageHeader, RawBinaryWriter,
    detect_file_format, open_dump_for_reading
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
#  Worker Thread Base
# ─────────────────────────────────────────────────────────────
class NANDWorker(QThread):
    """Base QThread worker for async NAND operations."""
    progress  = pyqtSignal(OperationProgress)
    completed = pyqtSignal(OperationProgress)
    log_msg   = pyqtSignal(str, str)    # (level, message)

    def __init__(self, engine: "NANDEngine", op: OperationProgress):
        super().__init__()
        self._engine = engine
        self._op     = op
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def _emit_log(self, level: str, msg: str):
        self.log_msg.emit(level, msg)

    def run(self):
        try:
            self.execute()
        except Exception as e:
            self._op.fail(str(e))
            self._emit_log("error", f"Worker exception: {e}")
        finally:
            self.completed.emit(self._op)

    def execute(self):
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────
#  Worker: Read Full Dump
# ─────────────────────────────────────────────────────────────
class ReadWorker(NANDWorker):
    page_data = pyqtSignal(int, bytes)   # (page_num, data)

    def execute(self):
        engine = self._engine
        op     = self._op
        dev    = engine.device_info

        op.start()
        op.op_type     = OperationType.READ_FULL_DUMP
        op.total       = dev.total_pages
        op.bytes_total = dev.total_size_bytes

        out_path = engine.session.output_file
        use_ecc  = engine.session.use_ecc

        # Choose file format writer
        ext = os.path.splitext(out_path)[1].lower()
        use_nandimg = (ext == ".nandimg")

        try:
            if use_nandimg:
                ecc_mode = engine.ecc.mode if engine.ecc else "none"
                hdr = NANDImageHeader.from_device(
                    dev,
                    include_oob=engine.session.include_oob,
                    ecc_mode=ecc_mode
                )
                writer_ctx = NANDImageWriter(out_path, hdr)
            else:
                writer_ctx = RawBinaryWriter(out_path)

            with writer_ctx as writer:
                for page in range(dev.total_pages):
                    if self._cancel.is_set():
                        op.cancel()
                        return

                    block = page // dev.pages_per_block
                    if engine.session.skip_bad_blocks:
                        if engine.bad_block_map.is_bad(block):
                            writer.write_page(b"\xFF" * dev.page_size)
                            op.current += 1
                            continue

                    raw = engine.serial.read_page(page, read_oob=True)
                    if raw is None:
                        op.warnings.append(f"Failed to read page {page}")
                        writer.write_page(b"\xFF" * dev.page_size)
                        op.current += 1
                        continue

                    data = raw[:dev.page_size]
                    oob  = raw[dev.page_size:] if len(raw) > dev.page_size else b""

                    # ECC check
                    if use_ecc and oob and engine.ecc:
                        stored_ecc = engine.ecc.extract_ecc_from_oob(oob)
                        data_arr   = bytearray(data)
                        result     = engine.ecc.check_and_correct_page(
                                         data_arr, stored_ecc)
                        data = bytes(data_arr)
                        if result.corrected_bits:
                            op.ecc_corrected += result.corrected_bits
                        if result.uncorrectable:
                            op.ecc_errors += result.uncorrectable
                            op.errors.append(f"Page {page}: uncorrectable ECC error")

                    # Include OOB if requested
                    page_out = data
                    if engine.session.include_oob and oob:
                        page_out = data + oob

                    writer.write_page(page_out)
                    self.page_data.emit(page, data)

                    op.current        += 1
                    op.bytes_processed += len(data)

                    if op.current % 16 == 0:
                        self.progress.emit(op)

                # Embed bad block list in .nandimg header
                if use_nandimg and hasattr(writer, 'header'):
                    writer.header.bad_blocks = list(engine.bad_block_map.bad_blocks)

        except OSError as e:
            op.fail(f"File I/O error: {e}")
            return

        op.complete()
        self._emit_log("info",
            f"Read complete: {op.total} pages, "
            f"{op.ecc_corrected} ECC corrections, "
            f"{op.ecc_errors} uncorrectable errors"
        )


# ─────────────────────────────────────────────────────────────
#  Worker: Write Full Dump
# ─────────────────────────────────────────────────────────────
class WriteWorker(NANDWorker):
    def execute(self):
        engine = self._engine
        op     = self._op
        dev    = engine.device_info

        op.start()
        op.op_type = OperationType.WRITE_FULL_DUMP

        src_path = engine.session.source_file

        # Open appropriate reader
        try:
            reader, header = open_dump_for_reading(
                src_path,
                page_size=dev.page_size,
                oob_size=dev.oob_size
            )
        except (OSError, ValueError) as e:
            op.fail(f"Cannot open source file: {e}")
            return

        # Determine total pages
        if header:
            total_pages = header.total_pages or (
                os.path.getsize(src_path) // header.page_size
            )
        else:
            total_pages = reader.total_pages

        op.total       = total_pages
        op.bytes_total = total_pages * dev.page_size

        try:
            for page_num, page_data in reader.iter_pages():
                if self._cancel.is_set():
                    op.cancel()
                    return

                # Trim to page_size if OOB is appended
                page_data = page_data[:dev.page_size]
                if len(page_data) < dev.page_size:
                    page_data = page_data.ljust(dev.page_size, b"\xFF")

                block = page_num // dev.pages_per_block
                if engine.session.skip_bad_blocks:
                    if engine.bad_block_map.is_bad(block):
                        op.current += 1
                        continue

                # Erase block on first page of each block
                if page_num % dev.pages_per_block == 0:
                    ok = engine.serial.erase_block(block)
                    if not ok:
                        op.errors.append(f"Erase failed block {block}")

                ok = engine.serial.write_page(page_num, page_data)
                if not ok:
                    op.errors.append(f"Write failed page {page_num}")

                op.current        += 1
                op.bytes_processed += len(page_data)

                if op.current % 16 == 0:
                    self.progress.emit(op)

        except OSError as e:
            op.fail(f"File I/O error: {e}")
            return
        finally:
            if hasattr(reader, 'close'):
                reader.close()

        op.complete()
        self._emit_log("info",
            f"Write complete: {op.current}/{op.total} pages, "
            f"{len(op.errors)} errors"
        )


# ─────────────────────────────────────────────────────────────
#  Worker: Clone (Read Source → Write Destination)
# ─────────────────────────────────────────────────────────────
class CloneWorker(NANDWorker):
    def execute(self):
        engine  = self._engine
        op      = self._op
        dev     = engine.device_info

        op.start()
        op.op_type   = OperationType.CLONE
        op.total     = dev.total_pages * 2  # read + write passes
        op.bytes_total = dev.total_size_bytes * 2

        # ── Phase 1: Read source chip to memory buffer ──
        self._emit_log("info", "Clone Phase 1: Reading source chip…")
        dump = io.BytesIO()

        for page in range(dev.total_pages):
            if self._cancel.is_set(): op.cancel(); return

            block = page // dev.pages_per_block
            if engine.session.skip_bad_blocks and engine.bad_block_map.is_bad(block):
                dump.write(b"\xFF" * dev.page_size)
                op.current += 1
                continue

            raw = engine.serial.read_page(page, read_oob=False)
            data = raw[:dev.page_size] if raw else b"\xFF" * dev.page_size
            dump.write(data)

            op.current        += 1
            op.bytes_processed += dev.page_size
            if op.current % 16 == 0:
                self.progress.emit(op)

        # ── Phase 2: Write to destination (same chip after reconnect prompt) ──
        # In a real scenario the user would swap chips; here we write back
        self._emit_log("info", "Clone Phase 2: Programming destination chip…")
        dump.seek(0)

        for page in range(dev.total_pages):
            if self._cancel.is_set(): op.cancel(); return

            page_data = dump.read(dev.page_size)
            if not page_data:
                break

            block = page // dev.pages_per_block
            if engine.session.skip_bad_blocks and engine.bad_block_map.is_bad(block):
                op.current += 1
                continue

            if page % dev.pages_per_block == 0:
                engine.serial.erase_block(block)

            ok = engine.serial.write_page(page, page_data)
            if not ok:
                op.errors.append(f"Write failed page {page}")

            op.current        += 1
            op.bytes_processed += dev.page_size
            if op.current % 16 == 0:
                self.progress.emit(op)

        op.complete()


# ─────────────────────────────────────────────────────────────
#  Worker: Scan Bad Blocks
# ─────────────────────────────────────────────────────────────
class ScanWorker(NANDWorker):
    bad_block_found = pyqtSignal(int)

    def execute(self):
        engine = self._engine
        op     = self._op

        op.start()
        op.op_type = OperationType.SCAN_BAD_BLOCKS
        op.total   = engine.device_info.total_blocks

        def on_progress(cur, total, bad_count):
            op.current = cur
            op.total   = total
            self.progress.emit(op)

        bad_list = engine.serial.scan_bad_blocks(progress_cb=on_progress)
        if bad_list is None:
            op.fail("Scan bad blocks command failed")
            return

        # Update bad block map
        engine.bad_block_map.total_blocks = engine.device_info.total_blocks
        for blk in bad_list:
            engine.bad_block_map.mark_bad(blk)
            op.bad_blocks.append(blk)
            self.bad_block_found.emit(blk)

        op.complete()
        self._emit_log("info",
            f"Scan complete: {len(bad_list)} bad blocks "
            f"({engine.bad_block_map.bad_percentage:.2f}%)"
        )


# ─────────────────────────────────────────────────────────────
#  Worker: Erase All
# ─────────────────────────────────────────────────────────────
class EraseWorker(NANDWorker):
    def execute(self):
        engine = self._engine
        op     = self._op
        dev    = engine.device_info

        op.start()
        op.op_type = OperationType.ERASE_ALL
        op.total   = dev.total_blocks

        for block in range(dev.total_blocks):
            if self._cancel.is_set():
                op.cancel()
                return

            if engine.session.skip_bad_blocks and engine.bad_block_map.is_bad(block):
                op.current += 1
                continue

            ok = engine.serial.erase_block(block)
            if not ok:
                op.errors.append(f"Erase failed block {block}")
            op.current += 1

            if op.current % 8 == 0:
                self.progress.emit(op)

        op.complete()
        self._emit_log("info",
            f"Erase complete: {op.current} blocks, {len(op.errors)} errors"
        )


# ─────────────────────────────────────────────────────────────
#  Worker: Verify (compare chip vs dump file page-by-page)
# ─────────────────────────────────────────────────────────────
class VerifyWorker(NANDWorker):
    """Compare chip contents page-by-page against a reference dump file."""

    def __init__(self, engine: "NANDEngine", op: OperationProgress, src: str):
        super().__init__(engine, op)
        self._src = src

    def execute(self):
        engine = self._engine
        op     = self._op
        dev    = engine.device_info

        op.start()
        op.op_type = OperationType.VERIFY

        try:
            reader, header = open_dump_for_reading(
                self._src, page_size=dev.page_size, oob_size=dev.oob_size
            )
        except (OSError, ValueError) as e:
            op.fail(f"Cannot open verify file: {e}")
            return

        total = (header.total_pages if header and header.total_pages
                 else reader.total_pages)
        op.total = total
        mismatch_count = 0

        try:
            for page_num, ref_data in reader.iter_pages():
                if self._cancel.is_set():
                    op.cancel()
                    return

                ref_page = ref_data[:dev.page_size]
                block = page_num // dev.pages_per_block
                if engine.session.skip_bad_blocks and engine.bad_block_map.is_bad(block):
                    op.current += 1
                    continue

                chip_raw = engine.serial.read_page(page_num, read_oob=False)
                if chip_raw is None:
                    op.errors.append(f"Read failed for page {page_num}")
                    op.current += 1
                    continue

                chip_page = chip_raw[:dev.page_size]
                if chip_page != ref_page:
                    mismatch_count += 1
                    op.errors.append(f"Mismatch at page {page_num}")

                op.current        += 1
                op.bytes_processed += dev.page_size

                if op.current % 32 == 0:
                    self.progress.emit(op)

        except OSError as e:
            op.fail(f"File I/O error during verify: {e}")
            return
        finally:
            if hasattr(reader, 'close'):
                reader.close()

        op.complete()
        if mismatch_count == 0:
            self._emit_log("success",
                f"Verify PASSED — all {op.total} pages match")
        else:
            self._emit_log("error",
                f"Verify FAILED — {mismatch_count} page mismatches out of {op.total}")


# ─────────────────────────────────────────────────────────────
#  NAND Engine (Main Facade)
# ─────────────────────────────────────────────────────────────
class NANDEngine(QObject):
    """
    Main NAND operations engine.
    
    Coordinates serial communication, ECC, and all NAND operations.
    Emits PyQt6 signals for GUI integration.
    """

    # Signals
    connection_changed  = pyqtSignal(bool, str)        # (connected, message)
    device_detected     = pyqtSignal(DeviceInfo)
    operation_started   = pyqtSignal(OperationProgress)
    operation_progress  = pyqtSignal(OperationProgress)
    operation_completed = pyqtSignal(OperationProgress)
    log_message         = pyqtSignal(str, str)          # (level, text)
    bad_block_found     = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.serial       = SerialManager()
        self.device_info  = DeviceInfo()
        self.bad_block_map = BadBlockMap()
        self.ecc: Optional[ECCEngine] = None
        self.session      = NANDSession()
        self._worker: Optional[NANDWorker] = None

    # ── Connection ────────────────────────────────────────────
    def connect(self, port: str) -> bool:
        ok = self.serial.connect(port)
        if ok:
            fw = self.serial.get_firmware_version()
            self.device_info.firmware_ver = fw or "Unknown"
            self.device_info.port = port
            self.device_info.connected = True
            self.connection_changed.emit(True, f"Connected to {port} (FW {fw})")
            self.log("info", f"Connected to Teensy on {port}, firmware {fw}")
        else:
            self.connection_changed.emit(False, f"Failed to connect to {port}")
            self.log("error", f"Connection failed: {port}")
        return ok

    def disconnect(self):
        self.serial.disconnect()
        self.device_info.connected = False
        self.connection_changed.emit(False, "Disconnected")
        self.log("info", "Disconnected from serial port")

    # ── Device Detection ──────────────────────────────────────
    def detect_device(self) -> bool:
        if not self.serial.connected:
            self.log("error", "Not connected")
            return False

        self.log("info", "Detecting NAND Flash chip…")
        
        # Power on
        self.serial.set_power(True)
        time.sleep(0.1)

        raw = self.serial.nand_detect()
        if not raw:
            self.log("error", "No NAND Flash chip detected")
            return False

        dev = self.device_info
        dev.mfr_id          = raw["mfr_id"]
        dev.dev_id          = raw["dev_id"]
        dev.id_bytes        = raw["id_bytes"]
        dev.page_size       = raw["page_size"]
        dev.oob_size        = raw["oob_size"]
        dev.pages_per_block = raw["pages_per_block"]
        dev.blocks_per_lun  = raw["blocks_per_lun"]
        dev.luns            = raw["luns"]
        dev.col_addr_cycles = raw["col_addr_cycles"]
        dev.row_addr_cycles = raw["row_addr_cycles"]
        dev.onfi_compliant  = raw["onfi_compliant"]
        dev.onfi_mfr        = raw["onfi_mfr"]
        dev.onfi_model      = raw["onfi_model"]

        # Look up in database
        chip = fast_lookup(dev.mfr_id, dev.dev_id)
        if chip:
            dev.manufacturer = chip.manufacturer
            dev.model        = chip.part_number
            ecc_mode = ECCEngine().recommend_mode(chip.ecc_bits_required)
            self.ecc = ECCEngine(mode=ecc_mode,
                                 page_size=dev.page_size,
                                 oob_size=dev.oob_size)
            self.log("info", f"Known chip: {chip.manufacturer} {chip.part_number}")
        else:
            dev.manufacturer = get_manufacturer_name(dev.mfr_id)
            dev.model        = f"0x{dev.dev_id:02X} (Unknown)"
            self.ecc = ECCEngine(mode=ECCEngine.MODE_HAMMING,
                                 page_size=dev.page_size,
                                 oob_size=dev.oob_size)
            self.log("warning", f"Unknown chip ID 0x{dev.mfr_id:02X}/0x{dev.dev_id:02X}")

        # Update session
        self.session.device = dev
        self.bad_block_map = BadBlockMap(total_blocks=dev.total_blocks)
        self.session.bad_block_map = self.bad_block_map

        self.log("info",
            f"NAND detected: {dev.manufacturer} {dev.model} "
            f"| {dev.total_size_mb:.1f} MB "
            f"| {dev.page_size}B pages / {dev.pages_per_block} pages per block "
            f"| {dev.total_blocks} blocks"
        )
        self.device_detected.emit(dev)
        return True

    # ── Operation Launchers ───────────────────────────────────
    def _start_worker(self, worker: NANDWorker):
        if self._worker and self._worker.isRunning():
            self.log("error", "Another operation is already running")
            return
        self._worker = worker
        worker.progress.connect(self.operation_progress)
        worker.completed.connect(self._on_worker_done)
        worker.log_msg.connect(self.log_message)
        self.operation_started.emit(worker._op)
        worker.start()

    def _on_worker_done(self, op: OperationProgress):
        self.operation_completed.emit(op)
        self._worker = None

    def read_chip(self, output_path: str):
        """Read full chip to file."""
        self.session.output_file = output_path
        op = OperationProgress(op_type=OperationType.READ_FULL_DUMP)
        worker = ReadWorker(self, op)
        self._start_worker(worker)

    def write_chip(self, source_path: str):
        """Write file to chip."""
        self.session.source_file = source_path
        op = OperationProgress(op_type=OperationType.WRITE_FULL_DUMP)
        worker = WriteWorker(self, op)
        self._start_worker(worker)

    def clone_chip(self):
        """Clone chip (read then write)."""
        op = OperationProgress(op_type=OperationType.CLONE)
        worker = CloneWorker(self, op)
        self._start_worker(worker)

    def scan_bad_blocks(self):
        """Scan all blocks for bad blocks."""
        op = OperationProgress(op_type=OperationType.SCAN_BAD_BLOCKS)
        worker = ScanWorker(self, op)
        worker.bad_block_found.connect(self.bad_block_found)
        self._start_worker(worker)

    def erase_chip(self):
        """Erase all blocks."""
        op = OperationProgress(op_type=OperationType.ERASE_ALL)
        worker = EraseWorker(self, op)
        self._start_worker(worker)

    def verify_chip(self, source_path: str):
        """Verify chip contents against a dump file."""
        op = OperationProgress(op_type=OperationType.VERIFY)
        worker = VerifyWorker(self, op, source_path)
        self._start_worker(worker)

    def cancel_operation(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.log("warning", "Cancel requested…")

    def read_single_page(self, page_num: int) -> Optional[bytes]:
        """Synchronous single page read."""
        return self.serial.read_page(page_num, read_oob=True)

    # ── Helpers ───────────────────────────────────────────────
    def log(self, level: str, message: str):
        self.log_message.emit(level, message)
        getattr(logger, level, logger.info)(message)

    def get_available_ports(self) -> list:
        return self.serial.list_ports()

    def is_busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def get_stats(self) -> dict:
        return self.serial.get_stats()
