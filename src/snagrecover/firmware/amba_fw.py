"""Ambarella firmware handling."""

import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .firmware import Firmware, FirmwareError

# Firmware file offsets
FIRM_OFFSET_VERSION = 0x3C
FIRM_OFFSET_MEMFW_RESULT = 0x40
FIRM_OFFSET_MEMFW_CMD = 0x50
FIRM_OFFSET_MEMFW_PROG = 0x60

# Board info constants
BOARD_INFO_MAGIC = 0x12345678
BOARD_INFO_ADDR = 0x100000
PTB_PTR = 0x200000

# Firmware info constants
FW_INFO_MAGIC = 0x87654321
FW_INFO_ADDR = 0x110000

@dataclass
class AmbaFirmwareInfo:
    """Ambarella firmware information."""
    version: int
    memfw_result_addr: int
    memfw_cmd_addr: int
    memfw_prog_addr: int

class AmbaFirmware(Firmware):
    """Ambarella firmware handler."""

    def __init__(self, bootloader_path: Optional[Path] = None,
                 dram_script_path: Optional[Path] = None):
        """Initialize firmware handler.
        
        Args:
            bootloader_path: Path to bootloader binary
            dram_script_path: Path to DRAM initialization script
        """
        super().__init__()
        self.bootloader_path = bootloader_path
        self.dram_script_path = dram_script_path
        self._bootloader_data: Optional[bytes] = None
        self._dram_script_data: Optional[str] = None

    def load(self) -> None:
        """Load firmware files.
        
        Raises:
            FirmwareError: If loading fails
        """
        # Load bootloader if specified
        if self.bootloader_path:
            try:
                with open(self.bootloader_path, 'rb') as f:
                    self._bootloader_data = f.read()
            except OSError as e:
                raise FirmwareError(f"Failed to load bootloader: {e}")

        # Load DRAM script if specified
        if self.dram_script_path:
            try:
                with open(self.dram_script_path, 'r') as f:
                    self._dram_script_data = f.read()
            except OSError as e:
                raise FirmwareError(f"Failed to load DRAM script: {e}")

    @property
    def bootloader(self) -> bytes:
        """Get bootloader data.
        
        Returns:
            Bootloader binary data
            
        Raises:
            FirmwareError: If bootloader not loaded
        """
        if not self._bootloader_data:
            raise FirmwareError("Bootloader not loaded")
        return self._bootloader_data

    @property
    def dram_script(self) -> str:
        """Get DRAM initialization script.
        
        Returns:
            DRAM script content
            
        Raises:
            FirmwareError: If script not loaded
        """
        if not self._dram_script_data:
            raise FirmwareError("DRAM script not loaded")
        return self._dram_script_data

    @staticmethod
    def get_firmware_info(firmware_path: Path) -> AmbaFirmwareInfo:
        """Extract firmware information from file.
        
        Args:
            firmware_path: Path to firmware file
            
        Returns:
            Firmware information
            
        Raises:
            FirmwareError: If extraction fails
        """
        try:
            with open(firmware_path, 'rb') as f:
                # Read firmware info fields
                f.seek(FIRM_OFFSET_VERSION)
                version = struct.unpack('<I', f.read(4))[0]
                
                f.seek(FIRM_OFFSET_MEMFW_RESULT)
                result_addr = struct.unpack('<I', f.read(4))[0]
                
                f.seek(FIRM_OFFSET_MEMFW_CMD)
                cmd_addr = struct.unpack('<I', f.read(4))[0]
                
                f.seek(FIRM_OFFSET_MEMFW_PROG)
                prog_addr = struct.unpack('<I', f.read(4))[0]

            return AmbaFirmwareInfo(
                version=version,
                memfw_result_addr=result_addr,
                memfw_cmd_addr=cmd_addr,
                memfw_prog_addr=prog_addr
            )

        except (OSError, struct.error) as e:
            raise FirmwareError(f"Failed to extract firmware info: {e}")

    @staticmethod
    def pack_board_info() -> bytes:
        """Pack board information structure.
        
        Returns:
            Packed board info data
        """
        return struct.pack('<IIII',
                         BOARD_INFO_MAGIC,  # magic
                         0x6F547541,        # 'AuTo' in little endian
                         PTB_PTR,           # PTB pointer
                         0)                 # reserved

    @staticmethod
    def pack_firmware_info(fw_info: AmbaFirmwareInfo) -> bytes:
        """Pack firmware information structure.
        
        Args:
            fw_info: Firmware information
            
        Returns:
            Packed firmware info data
        """
        return struct.pack('<IIII',
                         FW_INFO_MAGIC,           # magic
                         fw_info.memfw_cmd_addr,  # command address
                         fw_info.memfw_result_addr,  # result address
                         0)                       # reserved
