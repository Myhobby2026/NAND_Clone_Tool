# NAND Flash Clone Tool

**Professional NAND Flash Memory Programmer & Clone Utility for Windows**
Powered by Teensy 4.1 hardware bridge · Python 3 / PyQt6

---

## Overview

NAND Flash Clone Tool is a professional-grade utility for reading, writing, erasing, and cloning NAND Flash memory chips. It uses a Teensy 4.1 microcontroller as a hardware bridge connected over USB serial, and provides a modern dark-themed GUI with full chip support, ECC correction, bad block management, and hex visualization.

---

## Features

| Feature | Details |
|---------|---------|
| **Read** | Full chip dump to binary, .nandimg (with metadata + SHA256) |
| **Write** | Program chip from dump file with block erase before write |
| **Erase** | Chip-level or range erase with bad block preservation |
| **Clone** | Chip-to-chip clone (read → buffer → write) |
| **Scan Bad Blocks** | Scan entire chip, display bad block map |
| **ECC** | Hamming (1-bit/256B), BCH-4/8/12/24 (multi-bit/512B or 1KB) |
| **Hex Viewer** | Page-by-page hex+ASCII viewer with search & goto |
| **Block Map** | Visual grid showing good/bad/written/erased blocks |
| **Chip Database** | Samsung, Micron, Toshiba, SK Hynix, Macronix, Nanya |
| **ONFI** | Auto-detect ONFI-compliant chips and read parameter page |
| **Log** | Color-coded timestamped operation log with export |

---

## Requirements

### Software
- **Python** 3.10 or newer — [python.org](https://python.org)
- **PyQt6** 6.7+ (GUI)
- **pyserial** 3.5+ (Serial communication)
- **Windows** 10 / 11 (64-bit)

### Hardware
- **Teensy 4.1** — [pjrc.com](https://www.pjrc.com/store/teensy41.html)
- NAND Flash chip in TSOP48, BGA152, or BGA132 package
- ZIF socket for TSOP48 chips (recommended)
- P-channel MOSFET for VCC switching (e.g., AO3401A)
- USB-A to Micro-USB cable

---

## Quick Start

### 1. Install Dependencies

```bat
setup.bat
```

Or manually:
```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Flash Teensy Firmware

1. Open **Arduino IDE** or **Teensyduino**
2. Open `firmware\nand_flash_bridge\nand_flash_bridge.ino`
3. Set **Board** to `Teensy 4.1`
4. Set **USB Type** to `Serial`
5. Click **Upload**

### 3. Wire the Hardware

Connect Teensy 4.1 to NAND Flash chip as shown below:

| Teensy 4.1 Pin | Signal | NAND Pin | Notes |
|---------------|--------|----------|-------|
| 0 – 7 | I/O [0..7] | DQ[0..7] | 8-bit data bus |
| 8 | CLE | CLE | Command Latch Enable |
| 9 | ALE | ALE | Address Latch Enable |
| 10 | WE# | WE | Write Enable (active low) |
| 11 | RE# | RE | Read Enable (active low) |
| 12 | CE# | CE | Chip Enable (active low) |
| 13 | R/B# | R/B | Ready/Busy — add 10kΩ pullup |
| 14 | WP# | WP | Write Protect (active low) |
| 15 | VCC_EN | — | P-MOSFET gate for 3.3V power |
| 3.3V | VCC | VCC | Through P-MOSFET drain |
| GND | GND | VSS | Common ground |

> **Open the wiring guide in the app:** Help → Hardware Wiring Guide

### 4. Launch the Tool

```bat
launch.bat
```

Or:
```bat
python main.py
```

With auto-connect:
```bat
python main.py --port COM5
```

---

## Usage Guide

### Connecting

1. Plug in Teensy 4.1 via USB
2. In the toolbar, select the COM port (Teensy ports are marked with ★)
3. Click **Connect** — the status indicator turns green
4. Click **Detect Chip** (or press F5) to identify the NAND chip

### Reading a Chip

1. Go to the **Read** tab
2. Click **Browse…** and select an output file path
3. Choose format: Raw Binary (`.bin`) or NAND Image (`.nandimg`)
4. Configure ECC and bad block options
5. Click **▶ Start Read**

The `.nandimg` format embeds device metadata, bad block list, ECC mode, and SHA256 checksum.

### Writing to a Chip

1. Go to the **Write** tab
2. Browse to your dump file (`.bin`, `.nandimg`, `.img`)
3. Enable "Erase block before writing" (recommended)
4. Click **▶ Start Write**

> ⚠ A confirmation dialog will appear — this operation is irreversible.

### Cloning a Chip

1. Connect the source chip
2. Go to the **Clone** tab and click **⧉ Start Clone**
3. Phase 1 reads the source chip into RAM
4. Swap chips when prompted
5. Phase 2 programs the destination chip

### Bad Block Scanning

1. Go to the **Scan Blocks** tab
2. Click **🔍 Scan All Blocks**
3. Bad blocks appear in the table and are highlighted red on the Block Map

### Hex Viewer

- Go to the **Hex View** tab
- Use **Load Page** to read a single page from the chip
- Or use **File → Open** to browse any binary file
- Navigate with Prev/Next, or type an address in the Go-to box

---

## File Formats

### `.nandimg` (Recommended)
Custom binary format with metadata:
- Magic header + version
- JSON metadata (chip info, geometry, ECC mode, bad block list)
- Raw page data
- SHA256 checksum of data area

### `.bin` / `.img`
Plain binary dump — raw page data without metadata. Page size and geometry must be configured manually when opening.

---

## Building a Standalone Executable

```bat
build_exe.bat
```

This uses PyInstaller to create `dist\NANDFlashCloneTool.exe` — a single-file executable with no Python dependency.

---

## Supported Chips

| Manufacturer | Examples |
|-------------|---------|
| **Samsung** | K9F1G08, K9F2G08, K9F4G08, K9G8G08, K9GAG08, K9LBG08, K9ABG08 |
| **Micron** | MT29F1G08, MT29F2G08, MT29F4G08, MT29F8G08, MT29F16G08, MT29F32G08 |
| **Toshiba/Kioxia** | TC58NVG0S3, TC58NVG1S3, TC58NVG2S0, TC58NVG3S0, TC58NVG4T2, TC58NVG5T2 |
| **SK Hynix** | H27U1G8F2, H27U2G8F2, H27U4G8F2, H27UCG8T2, H27UBG8T2 |
| **Macronix** | MX30LF1G08, MX30LF2G18, MX60LF8G18 |
| **Nanya** | NT29F1G08, NT29F2G08 |

**ONFI-compliant chips** are auto-detected with full geometry from the parameter page.

---

## Project Structure

```
NAND_Flash/
├── main.py                        # Application entry point
├── requirements.txt               # Python dependencies
├── setup.bat                      # Windows setup script
├── launch.bat                     # Application launcher
├── build_exe.bat                  # PyInstaller build script
│
├── firmware/
│   └── nand_flash_bridge/
│       └── nand_flash_bridge.ino  # Teensy 4.1 Arduino firmware
│
└── src/
    ├── core/
    │   ├── serial_manager.py      # Binary serial protocol (CRC-16)
    │   ├── nand_engine.py         # High-level NAND operations + Qt workers
    │   └── ecc_engine.py          # Hamming + BCH ECC
    │
    ├── models/
    │   ├── nand_models.py         # DeviceInfo, OperationProgress, BadBlockMap
    │   └── chip_database.py       # NAND chip database (25+ chips)
    │
    ├── gui/
    │   ├── main_window.py         # Main application window
    │   ├── theme.py               # Dark QSS stylesheet
    │   ├── panels/
    │   │   ├── connection_panel.py
    │   │   ├── device_panel.py
    │   │   ├── read_panel.py
    │   │   ├── write_panel.py
    │   │   ├── erase_panel.py
    │   │   ├── clone_panel.py
    │   │   ├── scan_panel.py
    │   │   ├── hex_viewer.py
    │   │   ├── block_map_panel.py
    │   │   └── log_panel.py
    │   └── dialogs/
    │       ├── connect_dialog.py
    │       ├── about_dialog.py
    │       └── wiring_dialog.py
    │
    └── utils/
        ├── file_formats.py        # .nandimg / raw binary I/O
        └── settings.py            # AppSettings (QSettings) + logging
```

---

## Protocol Reference

### Serial Protocol (Host ↔ Teensy)

**Command frame (Host → Teensy):**
```
[CMD: 1 byte][LEN: 4 bytes LE][PAYLOAD: LEN bytes][CRC16: 2 bytes LE]
```

**Response frame (Teensy → Host):**
```
[STATUS: 1 byte][LEN: 4 bytes LE][DATA: LEN bytes][CRC16: 2 bytes LE]
```

CRC algorithm: **CRC-16/CCITT-FALSE** (poly 0x1021, init 0xFFFF)
Baud rate: **2,000,000** (2 Mbaud)

### Command Codes
| Cmd | Hex | Description |
|-----|-----|-------------|
| PING | 0x01 | Connection test |
| GET_FW_VERSION | 0x02 | Firmware version |
| NAND_DETECT | 0x10 | Auto-detect chip, return geometry |
| NAND_READ_ID | 0x11 | Read 8-byte JEDEC ID |
| NAND_RESET | 0x13 | Reset NAND chip |
| READ_PAGE | 0x20 | Read page + OOB |
| WRITE_PAGE | 0x30 | Write page |
| ERASE_BLOCK | 0x40 | Erase block |
| SCAN_BAD_BLOCKS | 0x50 | Full bad block scan |
| GET_STATUS | 0x60 | Hardware status byte |
| SET_POWER | 0x70 | Control VCC enable |
| SET_WP | 0x71 | Control WP# pin |

---

## Troubleshooting

**"No chip detected"**
- Check all wiring, especially CE#, WE#, RE#
- Verify 3.3V power is reaching the chip VCC pin
- Add decoupling capacitors (100nF) near chip VCC
- Try pressing "Reset NAND" from Device menu

**"CRC error"**
- USB cable quality issue — try a different cable
- Reduce USB hub interference: plug Teensy directly into PC

**"Write failed" / write errors**
- Ensure WP# (Write Protect) is not held low
- Use "Disable write protect" option in Write panel
- Chip may need erasing first

**"Uncorrectable ECC error"**
- Chip has grown bad pages — check bad block scan results
- Use BCH-8 or BCH-24 ECC mode for MLC/TLC chips
- The page data is permanently damaged

**High bad block count (>5%)**
- Chip is near or past its P/E cycle limit
- Consider the chip unusable if bad blocks exceed manufacturer spec

---

## License

MIT License — Free for personal and commercial use.

---

*Built with Python 3, PyQt6, and Arduino/Teensyduino.*
