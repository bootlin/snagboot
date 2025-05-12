"""Ambarella recovery implementation."""

import re
import time
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import List, Optional, Tuple

from ..firmware.amba_fw import AmbaFirmware, AmbaFirmwareInfo
from ..protocols.amba import AmbaCommand, AmbaProtocol, AmbaUsbError
from ..usb import UsbDevice

class AdsCommandType(IntEnum):
    """ADS script command types."""
    INVALID = 0
    WRITE = 1
    READ = 2
    POLL = 3
    USLEEP = 4
    SLEEP = 5

@dataclass
class AdsCommand:
    """ADS script command."""
    type: AdsCommandType
    addr: int = 0
    data: int = 0
    mask: int = 0

class AdsParser:
    """Parser for Ambarella ADS scripts."""

    def parse(self, script: str) -> List[AdsCommand]:
        """Parse ADS script into commands.
        
        Args:
            script: ADS script content
            
        Returns:
            List of parsed commands
        """
        commands = []
        
        # Split into lines and process each
        for line in script.splitlines():
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Parse command
            if cmd := self._parse_line(line):
                commands.append(cmd)

        return commands

    def _parse_line(self, line: str) -> Optional[AdsCommand]:
        """Parse single ADS script line.
        
        Args:
            line: Script line
            
        Returns:
            Parsed command or None if invalid
        """
        # Write command: w addr data [mask]
        if m := re.match(r'w\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)(?:\s+0x([0-9a-f]+))?', line, re.I):
            addr = int(m.group(1), 16)
            data = int(m.group(2), 16)
            mask = int(m.group(3), 16) if m.group(3) else 0xFFFFFFFF
            return AdsCommand(AdsCommandType.WRITE, addr, data, mask)

        # Read command: r addr
        if m := re.match(r'r\s+0x([0-9a-f]+)', line, re.I):
            addr = int(m.group(1), 16)
            return AdsCommand(AdsCommandType.READ, addr)

        # Poll command: p addr data mask
        if m := re.match(r'p\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)', line, re.I):
            addr = int(m.group(1), 16)
            data = int(m.group(2), 16)
            mask = int(m.group(3), 16)
            return AdsCommand(AdsCommandType.POLL, addr, data, mask)

        # Sleep commands: sleep/usleep time
        if m := re.match(r'(sleep|usleep)\s+(\d+)', line):
            cmd_type = AdsCommandType.SLEEP if m.group(1) == 'sleep' else AdsCommandType.USLEEP
            time_val = int(m.group(2))
            return AdsCommand(cmd_type, data=time_val)

        return None

class AmbarellaRecovery:
    """Ambarella device recovery implementation."""

    def __init__(self, device: UsbDevice):
        """Initialize recovery handler.
        
        Args:
            device: USB device to recover
        """
        self.device = device
        self.protocol = AmbaProtocol(device)
        self.firmware = AmbaFirmware()
        self._ads_parser = AdsParser()

    def _execute_ads_commands(self, commands: List[AdsCommand]) -> None:
        """Execute ADS script commands.
        
        Args:
            commands: Commands to execute
            
        Raises:
            AmbaUsbError: On execution error
        """
        for cmd in commands:
            if cmd.type == AdsCommandType.WRITE:
                # Send write command
                self.protocol.send_command(AmbaCommand.RDY_TO_RCV, cmd.addr)
                self.protocol.send_command(AmbaCommand.RCV_DATA, cmd.data)

            elif cmd.type == AdsCommandType.POLL:
                # Poll until value matches or timeout
                timeout = time.time() + 5.0  # 5 second timeout
                while time.time() < timeout:
                    rsp, val, _ = self.protocol.send_command(
                        AmbaCommand.INQUIRY_STATUS, cmd.addr)
                    if (val & cmd.mask) == (cmd.data & cmd.mask):
                        break
                    time.sleep(0.001)

            elif cmd.type in (AdsCommandType.SLEEP, AdsCommandType.USLEEP):
                # Sleep for specified time
                sleep_time = cmd.data / 1_000_000 if cmd.type == AdsCommandType.USLEEP else cmd.data
                time.sleep(sleep_time)

    def initialize_dram(self, dram_script: Path) -> None:
        """Initialize device DRAM.
        
        Args:
            dram_script: Path to DRAM initialization script
            
        Raises:
            AmbaUsbError: On initialization error
        """
        # Load and parse DRAM script
        self.firmware.dram_script_path = dram_script
        self.firmware.load()
        
        commands = self._ads_parser.parse(self.firmware.dram_script)
        self._execute_ads_commands(commands)

    def load_bootloader(self, bootloader: Path) -> None:
        """Load bootloader to device.
        
        Args:
            bootloader: Path to bootloader binary
            
        Raises:
            AmbaUsbError: On loading error
        """
        # Load bootloader
        self.firmware.bootloader_path = bootloader
        self.firmware.load()

        # Send bootloader
        self.protocol.send_file(0x0, self.firmware.bootloader)

        # Send board info
        board_info = AmbaFirmware.pack_board_info()
        self.protocol.send_file(AmbaFirmware.BOARD_INFO_ADDR, board_info)

    def flash_firmware(self, firmware: Path) -> None:
        """Flash firmware to device.
        
        Args:
            firmware: Path to firmware file
            
        Raises:
            AmbaUsbError: On flashing error
        """
        # Get firmware info
        fw_info = AmbaFirmware.get_firmware_info(firmware)

        # Send firmware info
        fw_info_data = AmbaFirmware.pack_firmware_info(fw_info)
        self.protocol.send_file(AmbaFirmware.FW_INFO_ADDR, fw_info_data)

        # Send board info again
        board_info = AmbaFirmware.pack_board_info()
        self.protocol.send_file(AmbaFirmware.BOARD_INFO_ADDR, board_info)

        # Send firmware
        with open(firmware, 'rb') as f:
            fw_data = f.read()
        self.protocol.send_file(fw_info.memfw_prog_addr, fw_data)
