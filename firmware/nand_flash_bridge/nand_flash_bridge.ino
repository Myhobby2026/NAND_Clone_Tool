/**
 * NAND Flash Memory Clone Tool - Teensy 4.1 Firmware
 * =====================================================
 * Professional NAND Flash Bridge Firmware
 * Hardware: Teensy 4.1
 * 
 * Supports: 8-bit NAND Flash (ONFI compatible)
 * Protocol: Custom binary serial protocol @ 2Mbaud
 * 
 * Pin Mapping (Teensy 4.1):
 *   NAND I/O[0..7]  → Digital pins 0-7
 *   CLE             → Pin 8
 *   ALE             → Pin 9
 *   WE#             → Pin 10
 *   RE#             → Pin 11
 *   CE#             → Pin 12
 *   R/B#            → Pin 13  (Ready/Busy - input with pullup)
 *   WP#             → Pin 14  (Write Protect - active low)
 *   VCC_EN          → Pin 15  (3.3V power control via MOSFET)
 * 
 * Protocol:
 *   Host → Teensy: [CMD:1][LEN:4][PAYLOAD:LEN][CRC16:2]
 *   Teensy → Host: [STATUS:1][LEN:4][DATA:LEN][CRC16:2]
 * 
 * Version: 1.0.0
 * Author: NAND Flash Tool
 */

#include <Arduino.h>
#include <stdint.h>

// ============================================================
//  Pin Definitions
// ============================================================
#define NAND_IO_BASE     0       // D0-D7 on pins 0-7
#define PIN_CLE          8
#define PIN_ALE          9
#define PIN_WE           10
#define PIN_RE           11
#define PIN_CE           12
#define PIN_RB           13
#define PIN_WP           14
#define PIN_VCC_EN       15

// ============================================================
//  Protocol Commands
// ============================================================
#define CMD_PING             0x01
#define CMD_GET_FW_VERSION   0x02
#define CMD_NAND_DETECT      0x10
#define CMD_NAND_READ_ID     0x11
#define CMD_NAND_READ_PARAM  0x12
#define CMD_NAND_RESET       0x13
#define CMD_READ_PAGE        0x20
#define CMD_READ_PAGE_OOB    0x21
#define CMD_WRITE_PAGE       0x30
#define CMD_ERASE_BLOCK      0x40
#define CMD_SCAN_BAD_BLOCKS  0x50
#define CMD_GET_STATUS       0x60
#define CMD_SET_POWER        0x70
#define CMD_SET_WP           0x71
#define CMD_BULK_READ        0x80
#define CMD_BULK_WRITE       0x81

// ============================================================
//  Response Status Codes
// ============================================================
#define STATUS_OK            0x00
#define STATUS_ERROR         0x01
#define STATUS_BUSY          0x02
#define STATUS_TIMEOUT       0x03
#define STATUS_BAD_BLOCK     0x04
#define STATUS_ECC_ERROR     0x05
#define STATUS_WRITE_PROTECT 0x06
#define STATUS_NAND_FAIL     0x07
#define STATUS_CRC_ERROR     0x08
#define STATUS_INVALID_CMD   0x09

// ============================================================
//  NAND Standard Commands
// ============================================================
#define NAND_CMD_READ1       0x00
#define NAND_CMD_READ2       0x30
#define NAND_CMD_READID      0x90
#define NAND_CMD_RESET       0xFF
#define NAND_CMD_PAGEPROG1   0x80
#define NAND_CMD_PAGEPROG2   0x10
#define NAND_CMD_ERASE1      0x60
#define NAND_CMD_ERASE2      0xD0
#define NAND_CMD_STATUS      0x70
#define NAND_CMD_READ_PARAM  0xEC
#define NAND_CMD_ONFI_SIG    0x20

// ============================================================
//  Constants
// ============================================================
#define FW_VERSION_MAJOR     1
#define FW_VERSION_MINOR     0
#define FW_VERSION_PATCH     0
#define SERIAL_BAUD          2000000
#define RB_TIMEOUT_MS        5000
#define MAX_PAGE_SIZE        8192   // Support up to 8KB pages
#define MAX_OOB_SIZE         448    // Max OOB for 8KB pages
#define PROTOCOL_HEADER_SZ   5      // CMD(1) + LEN(4)
#define PROTOCOL_CRC_SZ      2
#define RX_BUFFER_SIZE       (MAX_PAGE_SIZE + MAX_OOB_SIZE + 64)

// ============================================================
//  NAND Geometry (populated after detection)
// ============================================================
struct NANDGeometry {
  uint8_t  mfr_id;
  uint8_t  dev_id;
  uint8_t  id_bytes[8];
  uint16_t page_size;       // bytes
  uint16_t oob_size;        // bytes
  uint32_t pages_per_block;
  uint32_t blocks_per_lun;
  uint8_t  luns;
  uint8_t  bits_per_cell;
  uint8_t  col_addr_cycles;
  uint8_t  row_addr_cycles;
  bool     detected;
  bool     onfi_compliant;
  char     onfi_mfr[13];    // 12 chars + null
  char     onfi_model[21];  // 20 chars + null
};

NANDGeometry nand_geo;

// ============================================================
//  Timing macros (Teensy 4.1 @ 600MHz, each NOP ~1.67ns)
// ============================================================
#define NAND_tWP_NS   12    // WE# pulse width min
#define NAND_tRP_NS   12    // RE# pulse width min
#define NAND_tREA_NS  25    // RE# access time

#define NAND_DELAY_NS(ns) \
  do { \
    uint32_t _c = (uint32_t)((ns) * 0.6f); \
    if (_c == 0) _c = 1; \
    for (uint32_t _i = 0; _i < _c; _i++) __asm__ volatile("nop"); \
  } while(0)

// ============================================================
//  CRC-16/CCITT-FALSE
// ============================================================
uint16_t crc16(const uint8_t *data, uint32_t len) {
  uint16_t crc = 0xFFFF;
  while (len--) {
    crc ^= ((uint16_t)(*data++) << 8);
    for (uint8_t i = 0; i < 8; i++) {
      if (crc & 0x8000) crc = (crc << 1) ^ 0x1021;
      else              crc <<= 1;
    }
  }
  return crc;
}

// ============================================================
//  I/O Direction Helpers
// ============================================================
void setIOInput() {
  for (int i = 0; i < 8; i++) {
    pinMode(NAND_IO_BASE + i, INPUT);
  }
}

void setIOOutput() {
  for (int i = 0; i < 8; i++) {
    pinMode(NAND_IO_BASE + i, OUTPUT);
  }
}

void writeIO(uint8_t val) {
  for (int i = 0; i < 8; i++) {
    digitalWriteFast(NAND_IO_BASE + i, (val >> i) & 0x01);
  }
}

uint8_t readIO() {
  uint8_t val = 0;
  for (int i = 0; i < 8; i++) {
    if (digitalReadFast(NAND_IO_BASE + i)) val |= (1 << i);
  }
  return val;
}

// ============================================================
//  NAND Low-Level Operations
// ============================================================
void nandInit() {
  // Control signals - default inactive state
  pinMode(PIN_CLE, OUTPUT); digitalWriteFast(PIN_CLE, LOW);
  pinMode(PIN_ALE, OUTPUT); digitalWriteFast(PIN_ALE, LOW);
  pinMode(PIN_WE,  OUTPUT); digitalWriteFast(PIN_WE,  HIGH);
  pinMode(PIN_RE,  OUTPUT); digitalWriteFast(PIN_RE,  HIGH);
  pinMode(PIN_CE,  OUTPUT); digitalWriteFast(PIN_CE,  HIGH);  // Deselect
  pinMode(PIN_WP,  OUTPUT); digitalWriteFast(PIN_WP,  HIGH);  // WP disabled
  pinMode(PIN_VCC_EN, OUTPUT); digitalWriteFast(PIN_VCC_EN, LOW);
  
  // R/B# - input with pullup
  pinMode(PIN_RB, INPUT_PULLUP);
  
  // I/O bus - start as input
  setIOInput();
}

void nandSelectChip()   { digitalWriteFast(PIN_CE, LOW); }
void nandDeselectChip() { digitalWriteFast(PIN_CE, HIGH); }

bool nandWaitReady(uint32_t timeout_ms = RB_TIMEOUT_MS) {
  uint32_t start = millis();
  while (digitalReadFast(PIN_RB) == LOW) {
    if ((millis() - start) >= timeout_ms) return false;
  }
  return true;
}

void nandWriteCommand(uint8_t cmd) {
  setIOOutput();
  digitalWriteFast(PIN_CLE, HIGH);
  digitalWriteFast(PIN_ALE, LOW);
  digitalWriteFast(PIN_WE,  LOW);
  writeIO(cmd);
  NAND_DELAY_NS(NAND_tWP_NS);
  digitalWriteFast(PIN_WE, HIGH);
  digitalWriteFast(PIN_CLE, LOW);
  NAND_DELAY_NS(10);
}

void nandWriteAddress(uint8_t addr) {
  setIOOutput();
  digitalWriteFast(PIN_CLE, LOW);
  digitalWriteFast(PIN_ALE, HIGH);
  digitalWriteFast(PIN_WE,  LOW);
  writeIO(addr);
  NAND_DELAY_NS(NAND_tWP_NS);
  digitalWriteFast(PIN_WE, HIGH);
  NAND_DELAY_NS(10);
  digitalWriteFast(PIN_ALE, LOW);
}

void nandWriteAddressNoLatch(uint8_t addr) {
  // ALE stays high between multiple address cycles
  setIOOutput();
  digitalWriteFast(PIN_ALE, HIGH);
  digitalWriteFast(PIN_WE,  LOW);
  writeIO(addr);
  NAND_DELAY_NS(NAND_tWP_NS);
  digitalWriteFast(PIN_WE, HIGH);
  NAND_DELAY_NS(5);
}

void nandWriteData(uint8_t data) {
  setIOOutput();
  digitalWriteFast(PIN_WE, LOW);
  writeIO(data);
  NAND_DELAY_NS(NAND_tWP_NS);
  digitalWriteFast(PIN_WE, HIGH);
  NAND_DELAY_NS(5);
}

uint8_t nandReadData() {
  setIOInput();
  digitalWriteFast(PIN_RE, LOW);
  NAND_DELAY_NS(NAND_tREA_NS);
  uint8_t val = readIO();
  digitalWriteFast(PIN_RE, HIGH);
  NAND_DELAY_NS(10);
  return val;
}

// ============================================================
//  NAND Address Encoding
// ============================================================
void nandSendAddress(uint32_t row, uint32_t col,
                     uint8_t col_cycles, uint8_t row_cycles) {
  digitalWriteFast(PIN_ALE, HIGH);
  
  // Column address
  for (uint8_t i = 0; i < col_cycles; i++) {
    setIOOutput();
    digitalWriteFast(PIN_WE, LOW);
    writeIO((col >> (8 * i)) & 0xFF);
    NAND_DELAY_NS(NAND_tWP_NS);
    digitalWriteFast(PIN_WE, HIGH);
    NAND_DELAY_NS(5);
  }
  
  // Row address
  for (uint8_t i = 0; i < row_cycles; i++) {
    setIOOutput();
    digitalWriteFast(PIN_WE, LOW);
    writeIO((row >> (8 * i)) & 0xFF);
    NAND_DELAY_NS(NAND_tWP_NS);
    digitalWriteFast(PIN_WE, HIGH);
    NAND_DELAY_NS(5);
  }
  
  digitalWriteFast(PIN_ALE, LOW);
}

// ============================================================
//  NAND Operations
// ============================================================
uint8_t nandReadStatus() {
  nandSelectChip();
  nandWriteCommand(NAND_CMD_STATUS);
  uint8_t status = nandReadData();
  nandDeselectChip();
  return status;
}

void nandReset() {
  nandSelectChip();
  nandWriteCommand(NAND_CMD_RESET);
  delay(5);
  nandWaitReady(500);
  nandDeselectChip();
}

bool nandReadID(uint8_t *id_buf, uint8_t len) {
  nandSelectChip();
  nandWriteCommand(NAND_CMD_READID);
  nandWriteAddress(0x00);
  for (uint8_t i = 0; i < len; i++) {
    id_buf[i] = nandReadData();
  }
  nandDeselectChip();
  return true;
}

bool nandReadONFIParam(uint8_t *param_buf) {
  nandSelectChip();
  nandWriteCommand(NAND_CMD_READ_PARAM);
  nandWriteAddress(0x00);
  if (!nandWaitReady(1000)) {
    nandDeselectChip();
    return false;
  }
  // ONFI parameter page is 256 bytes, 3 copies
  for (uint16_t i = 0; i < 256; i++) {
    param_buf[i] = nandReadData();
  }
  nandDeselectChip();
  return true;
}

bool nandReadPage(uint32_t page_num, uint8_t *data_buf,
                  uint8_t *oob_buf, uint16_t page_size, uint16_t oob_size,
                  uint8_t col_cyc, uint8_t row_cyc) {
  nandSelectChip();
  nandWriteCommand(NAND_CMD_READ1);
  nandSendAddress(page_num, 0, col_cyc, row_cyc);
  nandWriteCommand(NAND_CMD_READ2);
  
  if (!nandWaitReady()) {
    nandDeselectChip();
    return false;
  }
  
  // Read data area
  for (uint16_t i = 0; i < page_size; i++) {
    data_buf[i] = nandReadData();
  }
  
  // Read OOB area
  if (oob_buf && oob_size > 0) {
    for (uint16_t i = 0; i < oob_size; i++) {
      oob_buf[i] = nandReadData();
    }
  }
  
  nandDeselectChip();
  return true;
}

bool nandWritePage(uint32_t page_num, const uint8_t *data_buf,
                   uint16_t page_size, uint8_t col_cyc, uint8_t row_cyc) {
  // Check write protect
  if (digitalReadFast(PIN_WP) == LOW) return false;
  
  nandSelectChip();
  nandWriteCommand(NAND_CMD_PAGEPROG1);
  nandSendAddress(page_num, 0, col_cyc, row_cyc);
  
  // Write data
  setIOOutput();
  digitalWriteFast(PIN_CLE, LOW);
  digitalWriteFast(PIN_ALE, LOW);
  for (uint16_t i = 0; i < page_size; i++) {
    nandWriteData(data_buf[i]);
  }
  
  nandWriteCommand(NAND_CMD_PAGEPROG2);
  
  if (!nandWaitReady()) {
    nandDeselectChip();
    return false;
  }
  
  uint8_t status = nandReadStatus();
  nandDeselectChip();
  
  // Bit 0: 0 = pass, 1 = fail
  return !(status & 0x01);
}

bool nandEraseBlock(uint32_t block_num, uint32_t pages_per_block,
                    uint8_t row_cyc) {
  // Check write protect
  if (digitalReadFast(PIN_WP) == LOW) return false;
  
  uint32_t row = block_num * pages_per_block;
  
  nandSelectChip();
  nandWriteCommand(NAND_CMD_ERASE1);
  
  // Row address only (no column for erase)
  digitalWriteFast(PIN_ALE, HIGH);
  for (uint8_t i = 0; i < row_cyc; i++) {
    setIOOutput();
    digitalWriteFast(PIN_WE, LOW);
    writeIO((row >> (8 * i)) & 0xFF);
    NAND_DELAY_NS(NAND_tWP_NS);
    digitalWriteFast(PIN_WE, HIGH);
    NAND_DELAY_NS(5);
  }
  digitalWriteFast(PIN_ALE, LOW);
  
  nandWriteCommand(NAND_CMD_ERASE2);
  
  if (!nandWaitReady(RB_TIMEOUT_MS)) {
    nandDeselectChip();
    return false;
  }
  
  uint8_t status = nandReadStatus();
  nandDeselectChip();
  
  return !(status & 0x01);
}

// ============================================================
//  ONFI Detection & Geometry Parsing
// ============================================================
bool detectNAND() {
  memset(&nand_geo, 0, sizeof(nand_geo));
  
  nandReset();
  delay(10);
  
  // Read 8-byte ID
  nandReadID(nand_geo.id_bytes, 8);
  
  nand_geo.mfr_id = nand_geo.id_bytes[0];
  nand_geo.dev_id = nand_geo.id_bytes[1];
  
  // Validate - FF or 00 means no chip
  if (nand_geo.mfr_id == 0xFF || nand_geo.mfr_id == 0x00) {
    return false;
  }
  
  // Try ONFI
  uint8_t onfi_sig[4];
  nandSelectChip();
  nandWriteCommand(NAND_CMD_READID);
  nandWriteAddress(NAND_CMD_ONFI_SIG);
  for (int i = 0; i < 4; i++) onfi_sig[i] = nandReadData();
  nandDeselectChip();
  
  if (onfi_sig[0] == 'O' && onfi_sig[1] == 'N' &&
      onfi_sig[2] == 'F' && onfi_sig[3] == 'I') {
    nand_geo.onfi_compliant = true;
    
    uint8_t param[256];
    if (nandReadONFIParam(param)) {
      // Parse ONFI parameter page
      memcpy(nand_geo.onfi_mfr,   param + 32, 12); nand_geo.onfi_mfr[12]  = 0;
      memcpy(nand_geo.onfi_model, param + 44, 20); nand_geo.onfi_model[20] = 0;
      
      nand_geo.page_size        = *(uint32_t*)(param + 80);
      nand_geo.oob_size         = *(uint16_t*)(param + 84);
      nand_geo.pages_per_block  = *(uint32_t*)(param + 92);
      nand_geo.blocks_per_lun   = *(uint32_t*)(param + 96);
      nand_geo.luns             = param[100];
      nand_geo.bits_per_cell    = param[102];
      
      // Address cycles
      nand_geo.col_addr_cycles  = (param[101] >> 0) & 0x0F;
      nand_geo.row_addr_cycles  = (param[101] >> 4) & 0x0F;
    }
  }
  
  // Fallback: decode from ID bytes if not ONFI
  if (!nand_geo.onfi_compliant || nand_geo.page_size == 0) {
    uint8_t b3 = nand_geo.id_bytes[3];
    uint8_t b4 = nand_geo.id_bytes[4];
    
    // Page size from bits 1:0 of byte 3
    switch (b3 & 0x03) {
      case 0: nand_geo.page_size = 1024; break;
      case 1: nand_geo.page_size = 2048; break;
      case 2: nand_geo.page_size = 4096; break;
      case 3: nand_geo.page_size = 8192; break;
    }
    
    // OOB size from bit 2 of byte 3
    nand_geo.oob_size = (b3 & 0x04) ? (nand_geo.page_size / 32) : (nand_geo.page_size / 16);
    
    // Block size from bits 5:4 of byte 3
    uint16_t block_pages;
    switch ((b3 >> 4) & 0x03) {
      case 0: block_pages = 32;  break;
      case 1: block_pages = 64;  break;
      case 2: block_pages = 128; break;
      case 3: block_pages = 256; break;
      default: block_pages = 64;
    }
    nand_geo.pages_per_block = block_pages;
    
    // Bit width: bit 6 of byte 3
    nand_geo.bits_per_cell = (b3 & 0x0C) ? 2 : 1;
    
    // Address cycles (common defaults)
    nand_geo.col_addr_cycles = (nand_geo.page_size <= 512) ? 1 : 2;
    nand_geo.row_addr_cycles = 3;
    
    // Estimate blocks from total density
    nand_geo.blocks_per_lun = 1024;
    nand_geo.luns = 1;
  }
  
  // Clamp page size to buffer limits
  if (nand_geo.page_size > MAX_PAGE_SIZE) nand_geo.page_size = MAX_PAGE_SIZE;
  if (nand_geo.oob_size  > MAX_OOB_SIZE)  nand_geo.oob_size  = MAX_OOB_SIZE;
  
  nand_geo.detected = true;
  return true;
}

// ============================================================
//  Serial Protocol
// ============================================================
uint8_t rx_buf[RX_BUFFER_SIZE];
uint8_t tx_buf[RX_BUFFER_SIZE + 16];

bool readExact(uint8_t *buf, uint32_t len, uint32_t timeout_ms = 5000) {
  uint32_t start = millis();
  uint32_t received = 0;
  while (received < len) {
    if (Serial.available()) {
      buf[received++] = Serial.read();
    } else if ((millis() - start) > timeout_ms) {
      return false;
    }
  }
  return true;
}

void sendResponse(uint8_t status, const uint8_t *data, uint32_t data_len) {
  uint32_t total = 1 + 4 + data_len + 2;  // status + len + data + crc
  
  tx_buf[0] = status;
  tx_buf[1] = (data_len >>  0) & 0xFF;
  tx_buf[2] = (data_len >>  8) & 0xFF;
  tx_buf[3] = (data_len >> 16) & 0xFF;
  tx_buf[4] = (data_len >> 24) & 0xFF;
  
  if (data && data_len > 0) {
    memcpy(tx_buf + 5, data, data_len);
  }
  
  uint16_t crc = crc16(tx_buf, 5 + data_len);
  tx_buf[5 + data_len]     = (crc >> 0) & 0xFF;
  tx_buf[5 + data_len + 1] = (crc >> 8) & 0xFF;
  
  Serial.write(tx_buf, total);
  Serial.flush();
}

void sendOK() { sendResponse(STATUS_OK, nullptr, 0); }
void sendError(uint8_t code = STATUS_ERROR) { sendResponse(code, nullptr, 0); }

// ============================================================
//  Command Handlers
// ============================================================
void handlePing() {
  const char *pong = "PONG";
  sendResponse(STATUS_OK, (const uint8_t*)pong, 4);
}

void handleGetVersion() {
  uint8_t ver[3] = { FW_VERSION_MAJOR, FW_VERSION_MINOR, FW_VERSION_PATCH };
  sendResponse(STATUS_OK, ver, 3);
}

void handleDetect() {
  bool found = detectNAND();
  if (!found) {
    sendError(STATUS_NAND_FAIL);
    return;
  }
  
  uint8_t resp[128];
  uint8_t pos = 0;
  
  resp[pos++] = nand_geo.mfr_id;
  resp[pos++] = nand_geo.dev_id;
  memcpy(resp + pos, nand_geo.id_bytes, 8); pos += 8;
  resp[pos++] = (nand_geo.page_size >> 0) & 0xFF;
  resp[pos++] = (nand_geo.page_size >> 8) & 0xFF;
  resp[pos++] = (nand_geo.oob_size >> 0) & 0xFF;
  resp[pos++] = (nand_geo.oob_size >> 8) & 0xFF;
  resp[pos++] = (nand_geo.pages_per_block >>  0) & 0xFF;
  resp[pos++] = (nand_geo.pages_per_block >>  8) & 0xFF;
  resp[pos++] = (nand_geo.pages_per_block >> 16) & 0xFF;
  resp[pos++] = (nand_geo.pages_per_block >> 24) & 0xFF;
  resp[pos++] = (nand_geo.blocks_per_lun >>  0) & 0xFF;
  resp[pos++] = (nand_geo.blocks_per_lun >>  8) & 0xFF;
  resp[pos++] = (nand_geo.blocks_per_lun >> 16) & 0xFF;
  resp[pos++] = (nand_geo.blocks_per_lun >> 24) & 0xFF;
  resp[pos++] = nand_geo.luns;
  resp[pos++] = nand_geo.bits_per_cell;
  resp[pos++] = nand_geo.col_addr_cycles;
  resp[pos++] = nand_geo.row_addr_cycles;
  resp[pos++] = nand_geo.onfi_compliant ? 1 : 0;
  memcpy(resp + pos, nand_geo.onfi_mfr,   13); pos += 13;
  memcpy(resp + pos, nand_geo.onfi_model, 21); pos += 21;
  
  sendResponse(STATUS_OK, resp, pos);
}

void handleReadID() {
  uint8_t id[8];
  nandReadID(id, 8);
  sendResponse(STATUS_OK, id, 8);
}

void handleReset() {
  nandReset();
  sendOK();
}

void handleReadPage(const uint8_t *payload, uint32_t len) {
  if (len < 4) { sendError(); return; }
  if (!nand_geo.detected) { sendError(STATUS_NAND_FAIL); return; }
  
  uint32_t page_num = payload[0] | ((uint32_t)payload[1] << 8) |
                      ((uint32_t)payload[2] << 16) | ((uint32_t)payload[3] << 24);
  bool read_oob = (len > 4) ? payload[4] : true;
  
  uint8_t data_buf[MAX_PAGE_SIZE];
  uint8_t oob_buf[MAX_OOB_SIZE];
  
  bool ok = nandReadPage(page_num, data_buf,
                         read_oob ? oob_buf : nullptr,
                         nand_geo.page_size,
                         read_oob ? nand_geo.oob_size : 0,
                         nand_geo.col_addr_cycles,
                         nand_geo.row_addr_cycles);
  
  if (!ok) { sendError(STATUS_NAND_FAIL); return; }
  
  uint32_t resp_len = nand_geo.page_size + (read_oob ? nand_geo.oob_size : 0);
  uint8_t *resp_buf = (uint8_t*)malloc(resp_len);
  if (!resp_buf) { sendError(STATUS_ERROR); return; }
  
  memcpy(resp_buf, data_buf, nand_geo.page_size);
  if (read_oob) memcpy(resp_buf + nand_geo.page_size, oob_buf, nand_geo.oob_size);
  
  sendResponse(STATUS_OK, resp_buf, resp_len);
  free(resp_buf);
}

void handleWritePage(const uint8_t *payload, uint32_t len) {
  if (len < 4 + nand_geo.page_size) { sendError(); return; }
  if (!nand_geo.detected)            { sendError(STATUS_NAND_FAIL); return; }
  
  uint32_t page_num = payload[0] | ((uint32_t)payload[1] << 8) |
                      ((uint32_t)payload[2] << 16) | ((uint32_t)payload[3] << 24);
  
  bool ok = nandWritePage(page_num, payload + 4,
                          nand_geo.page_size,
                          nand_geo.col_addr_cycles,
                          nand_geo.row_addr_cycles);
  
  ok ? sendOK() : sendError(STATUS_NAND_FAIL);
}

void handleEraseBlock(const uint8_t *payload, uint32_t len) {
  if (len < 4) { sendError(); return; }
  if (!nand_geo.detected) { sendError(STATUS_NAND_FAIL); return; }
  
  uint32_t block_num = payload[0] | ((uint32_t)payload[1] << 8) |
                       ((uint32_t)payload[2] << 16) | ((uint32_t)payload[3] << 24);
  
  bool ok = nandEraseBlock(block_num, nand_geo.pages_per_block,
                           nand_geo.row_addr_cycles);
  
  ok ? sendOK() : sendError(STATUS_NAND_FAIL);
}

void handleScanBadBlocks() {
  if (!nand_geo.detected) { sendError(STATUS_NAND_FAIL); return; }
  
  uint32_t total_blocks = nand_geo.blocks_per_lun * nand_geo.luns;
  uint32_t max_bad = total_blocks / 8 + 1;
  uint8_t *bad_map = (uint8_t*)calloc(max_bad, 1);
  if (!bad_map) { sendError(); return; }
  
  uint32_t bad_count = 0;
  uint8_t oob[MAX_OOB_SIZE];
  uint8_t data_dummy[MAX_PAGE_SIZE];
  
  for (uint32_t blk = 0; blk < total_blocks && blk < 4096; blk++) {
    // Read first page OOB of block
    uint32_t page = blk * nand_geo.pages_per_block;
    nandReadPage(page, data_dummy, oob, nand_geo.page_size,
                 nand_geo.oob_size, nand_geo.col_addr_cycles,
                 nand_geo.row_addr_cycles);
    
    // Bad block marker: byte 0 of OOB != 0xFF
    bool is_bad = (oob[0] != 0xFF);
    
    if (is_bad) {
      // Store bad block number (4 bytes each)
      if (bad_count < 1024) {
        bad_map[bad_count * 4 + 0] = (blk >>  0) & 0xFF;
        bad_map[bad_count * 4 + 1] = (blk >>  8) & 0xFF;
        bad_map[bad_count * 4 + 2] = (blk >> 16) & 0xFF;
        bad_map[bad_count * 4 + 3] = (blk >> 24) & 0xFF;
        bad_count++;
      }
    }
    
    // Send progress every 64 blocks
    if ((blk % 64) == 0) {
      uint8_t prog[8];
      prog[0] = 0xBB; // progress marker
      prog[1] = (blk >>  0) & 0xFF;
      prog[2] = (blk >>  8) & 0xFF;
      prog[3] = (blk >> 16) & 0xFF;
      prog[4] = (total_blocks >>  0) & 0xFF;
      prog[5] = (total_blocks >>  8) & 0xFF;
      prog[6] = (total_blocks >> 16) & 0xFF;
      prog[7] = bad_count & 0xFF;
      sendResponse(STATUS_BUSY, prog, 8);
    }
  }
  
  // Final response: count (4) + block list (count * 4)
  uint32_t resp_len = 4 + bad_count * 4;
  uint8_t *resp = (uint8_t*)malloc(resp_len);
  if (!resp) { free(bad_map); sendError(); return; }
  
  resp[0] = (bad_count >>  0) & 0xFF;
  resp[1] = (bad_count >>  8) & 0xFF;
  resp[2] = (bad_count >> 16) & 0xFF;
  resp[3] = (bad_count >> 24) & 0xFF;
  memcpy(resp + 4, bad_map, bad_count * 4);
  
  sendResponse(STATUS_OK, resp, resp_len);
  free(resp);
  free(bad_map);
}

void handleSetPower(const uint8_t *payload, uint32_t len) {
  bool enable = (len > 0) && payload[0];
  digitalWriteFast(PIN_VCC_EN, enable ? HIGH : LOW);
  if (enable) delay(10);
  sendOK();
}

void handleSetWP(const uint8_t *payload, uint32_t len) {
  bool protect = (len > 0) && payload[0];
  digitalWriteFast(PIN_WP, protect ? LOW : HIGH);
  sendOK();
}

void handleGetStatus() {
  uint8_t st[4];
  st[0] = nandReadStatus();
  st[1] = digitalReadFast(PIN_RB)     ? 1 : 0;
  st[2] = digitalReadFast(PIN_WP)     ? 0 : 1;  // 1 = write protected
  st[3] = digitalReadFast(PIN_VCC_EN) ? 1 : 0;
  sendResponse(STATUS_OK, st, 4);
}

// ============================================================
//  Main Command Dispatcher
// ============================================================
void processCommand(uint8_t cmd, const uint8_t *payload, uint32_t len) {
  switch (cmd) {
    case CMD_PING:            handlePing();                         break;
    case CMD_GET_FW_VERSION:  handleGetVersion();                   break;
    case CMD_NAND_DETECT:     handleDetect();                       break;
    case CMD_NAND_READ_ID:    handleReadID();                       break;
    case CMD_NAND_RESET:      handleReset();                        break;
    case CMD_READ_PAGE:       handleReadPage(payload, len);         break;
    case CMD_WRITE_PAGE:      handleWritePage(payload, len);        break;
    case CMD_ERASE_BLOCK:     handleEraseBlock(payload, len);       break;
    case CMD_SCAN_BAD_BLOCKS: handleScanBadBlocks();                break;
    case CMD_SET_POWER:       handleSetPower(payload, len);         break;
    case CMD_SET_WP:          handleSetWP(payload, len);            break;
    case CMD_GET_STATUS:      handleGetStatus();                    break;
    default:                  sendError(STATUS_INVALID_CMD);        break;
  }
}

// ============================================================
//  Arduino Entry Points
// ============================================================
void setup() {
  Serial.begin(SERIAL_BAUD);
  
  // Wait for serial with timeout
  uint32_t t = millis();
  while (!Serial && (millis() - t) < 3000);
  
  nandInit();
  
  // Power-on indicator
  pinMode(LED_BUILTIN, OUTPUT);
  for (int i = 0; i < 3; i++) {
    digitalWriteFast(LED_BUILTIN, HIGH); delay(100);
    digitalWriteFast(LED_BUILTIN, LOW);  delay(100);
  }
}

void loop() {
  // Wait for command header: [CMD:1][LEN:4]
  if (Serial.available() < PROTOCOL_HEADER_SZ) return;
  
  uint8_t cmd = Serial.read();
  uint8_t len_bytes[4];
  if (!readExact(len_bytes, 4, 1000)) {
    // Flush and ignore
    while (Serial.available()) Serial.read();
    return;
  }
  
  uint32_t payload_len = len_bytes[0] | ((uint32_t)len_bytes[1] << 8) |
                         ((uint32_t)len_bytes[2] << 16) | ((uint32_t)len_bytes[3] << 24);
  
  // Sanity check
  if (payload_len > (uint32_t)(MAX_PAGE_SIZE + MAX_OOB_SIZE + 64)) {
    while (Serial.available()) Serial.read();
    sendError(STATUS_INVALID_CMD);
    return;
  }
  
  // Read payload + CRC
  uint32_t total = payload_len + PROTOCOL_CRC_SZ;
  if (total > sizeof(rx_buf)) {
    sendError(STATUS_ERROR);
    return;
  }
  
  if (!readExact(rx_buf, total, 10000)) {
    sendError(STATUS_TIMEOUT);
    return;
  }
  
  // Verify CRC
  uint8_t header[5] = { cmd, len_bytes[0], len_bytes[1], len_bytes[2], len_bytes[3] };
  uint16_t exp_crc = crc16(header, 5);
  if (payload_len > 0) {
    // Combine: recalculate over header+payload
    // Simple approach: compute over all but last 2 bytes
    uint8_t *full = (uint8_t*)malloc(5 + payload_len);
    if (full) {
      memcpy(full, header, 5);
      memcpy(full + 5, rx_buf, payload_len);
      exp_crc = crc16(full, 5 + payload_len);
      free(full);
    }
  }
  
  uint16_t recv_crc = rx_buf[payload_len] | ((uint16_t)rx_buf[payload_len + 1] << 8);
  
  if (recv_crc != exp_crc) {
    sendError(STATUS_CRC_ERROR);
    return;
  }
  
  // LED blink on activity
  digitalWriteFast(LED_BUILTIN, HIGH);
  
  processCommand(cmd, rx_buf, payload_len);
  
  digitalWriteFast(LED_BUILTIN, LOW);
}
