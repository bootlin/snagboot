"""Ambarella USB protocol implementation."""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Tuple

from ..usb import UsbDevice, UsbError

# Command/Response signatures
CMD_SIGNATURE = 0x55434D44
RSP_SIGNATURE = 0x55525350

class AmbaUsbError(Exception):
    """Ambarella USB protocol error."""
    pass

class AmbaInquiryType(IntEnum):
    """Ambarella inquiry types."""
    CHIP = 0x00000001
    ADDR = 0x00000002
    REG = 0x00000003

class AmbaCommand(IntEnum):
    """Ambarella USB commands."""
    RDY_TO_RCV = 0
    RCV_DATA = 1
    RDY_TO_SND = 2
    SND_DATA = 3
    INQUIRY_STATUS = 4

class AmbaResponse(IntEnum):
    """Ambarella USB response status."""
    SUCCESS = 0
    FAILED = 1
    IN_BLD = 2

@dataclass
class AmbaDeviceInfo:
    """Ambarella device information."""
    chip_type: int
    dram_start: int

class AmbaProtocol:
    """Ambarella USB protocol implementation."""

    def __init__(self, device: UsbDevice):
        """Initialize protocol handler.
        
        Args:
            device: USB device to communicate with
        """
        self.device = device
        self._cmd_buf = bytearray(32)  # Command buffer
        self._rsp_buf = bytearray(16)  # Response buffer

    def _pack_command(self, cmd: int, *params) -> bytes:
        """Pack command and parameters into buffer.
        
        Args:
            cmd: Command ID
            *params: Command parameters
        
        Returns:
            Packed command buffer
        """
        struct.pack_into("<IIIIIIII", self._cmd_buf, 0,
                        CMD_SIGNATURE,  # signature
                        cmd,            # command
                        *(params + (0,) * (6 - len(params))))  # parameters
        return self._cmd_buf

    def _unpack_response(self) -> Tuple[int, int, int, int]:
        """Unpack response buffer.
        
        Returns:
            Tuple of (signature, response, param0, param1)
        """
        return struct.unpack_from("<IIII", self._rsp_buf)

    def send_command(self, cmd: int, *params) -> Tuple[int, int, int]:
        """Send command and receive response.
        
        Args:
            cmd: Command ID
            *params: Command parameters
        
        Returns:
            Tuple of (response, param0, param1)
            
        Raises:
            AmbaUsbError: On protocol error
        """
        try:
            # Send command
            cmd_buf = self._pack_command(cmd, *params)
            self.device.write(cmd_buf)

            # Read response
            self.device.read(self._rsp_buf)
            sig, rsp, p0, p1 = self._unpack_response()

            if sig != RSP_SIGNATURE:
                raise AmbaUsbError("Invalid response signature")

            return rsp, p0, p1

        except UsbError as e:
            raise AmbaUsbError(f"USB communication error: {e}")

    def get_device_info(self) -> AmbaDeviceInfo:
        """Get device information.
        
        Returns:
            Device information
            
        Raises:
            AmbaUsbError: On protocol error
        """
        # Get chip type
        rsp, chip, _ = self.send_command(AmbaCommand.INQUIRY_STATUS,
                                       AmbaInquiryType.CHIP)
        if rsp != AmbaResponse.SUCCESS:
            raise AmbaUsbError("Failed to get chip type")

        # Get DRAM start address
        rsp, dram_start, _ = self.send_command(AmbaCommand.INQUIRY_STATUS,
                                             AmbaInquiryType.ADDR)
        if rsp != AmbaResponse.SUCCESS:
            raise AmbaUsbError("Failed to get DRAM start address")

        return AmbaDeviceInfo(chip, dram_start)

    def send_file(self, addr: int, data: bytes) -> None:
        """Send file data to device.
        
        Args:
            addr: Target address
            data: Data to send
            
        Raises:
            AmbaUsbError: On protocol error
        """
        # Ready to receive
        rsp, _, _ = self.send_command(AmbaCommand.RDY_TO_RCV, addr)
        if rsp != AmbaResponse.SUCCESS:
            raise AmbaUsbError("Device not ready to receive")

        # Send data command
        rsp, _, _ = self.send_command(AmbaCommand.RCV_DATA)
        if rsp != AmbaResponse.SUCCESS:
            raise AmbaUsbError("Failed to initiate data transfer")

        # Send data
        try:
            self.device.write(data)
        except UsbError as e:
            raise AmbaUsbError(f"Failed to send data: {e}")

        # Get final status
        rsp, _, _ = self.send_command(AmbaCommand.RDY_TO_RCV, 
                                    0x80000000,  # FORCE_FINISH | LAST_TRANS
                                    addr)
        if rsp != AmbaResponse.SUCCESS:
            raise AmbaUsbError("Data transfer failed")
