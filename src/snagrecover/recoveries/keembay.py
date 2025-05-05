# This file is part of Snagboot
# Copyright (C) 2023 Bootlin
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""
Recovery module for Intel Keembay boards.
"""

import time
import usb
import logging
from snagrecover.config import recovery_config
from snagrecover.utils import access_error, get_usb, prettify_usb_addr
from snagrecover.firmware.firmware import run_firmware
from snagrecover.protocols.fastboot import FastbootDevice

logger = logging.getLogger("snagrecover")

# Intel Keembay USB VID:PID
KEEMBAY_VID = 0x8087
KEEMBAY_PID_RECOVERY = 0x0b39
KEEMBAY_PID_FASTBOOT = 0xda00

class KeembayDevice:
    """Class representing a Keembay device in recovery mode."""
    
    def __init__(self, usb_dev):
        self.usb_dev = usb_dev
        self.serialno = None
        self._get_serial_number()
    
    def _get_serial_number(self):
        """Get the device serial number."""
        try:
            self.serialno = self.usb_dev.serial_number
            # Transform device serial into consistent format if needed
            if self.serialno:
                # Ensure the serial number is in the expected format
                # This might need adjustment based on the actual format of Keembay serial numbers
                self.serialno = self.serialno.upper()
        except Exception as e:
            logger.warning(f"Failed to get serial number: {str(e)}")
            self.serialno = None
    
    def flash_fip(self, fip_path):
        """Flash the FIP (Firmware Image Package) to the device."""
        logger.info(f"Flashing FIP to Keembay device with serial: {self.serialno}")
        
        # Create a FastbootDevice instance for the device
        fb_dev = FastbootDevice(self.usb_dev)
        
        # Flash the FIP using the stage command
        fb_dev.stage(fip_path)
        
        logger.info("FIP flashed successfully")
        return True

def main():
    """Main recovery function for Keembay boards."""
    soc_model = recovery_config["soc_model"]
    usb_dev = get_usb(recovery_config["usb_path"])
    
    logger.info(f"Starting recovery for {soc_model} board")
    
    # Check if the device is in recovery mode
    if usb_dev.idVendor != KEEMBAY_VID or usb_dev.idProduct != KEEMBAY_PID_RECOVERY:
        access_error("Keembay device", f"Device is not in recovery mode. Expected VID:PID {KEEMBAY_VID:04x}:{KEEMBAY_PID_RECOVERY:04x}, got {usb_dev.idVendor:04x}:{usb_dev.idProduct:04x}")
    
    # Create a Keembay device instance
    keembay_dev = KeembayDevice(usb_dev)
    
    # Flash the FIP
    if "fip" in recovery_config["firmware"]:
        fip_path = recovery_config["firmware"]["fip"]["path"]
        logger.info(f"Flashing FIP from {fip_path}")
        keembay_dev.flash_fip(fip_path)
    else:
        logger.warning("No FIP firmware specified, skipping FIP flashing")
    
    # Wait for the device to reboot into fastboot mode
    logger.info("Waiting for device to reboot into fastboot mode...")
    rom_path = (usb_dev.bus, usb_dev.port_numbers)
    rom_devnum = usb_dev.address
    
    t0 = time.time()
    while time.time() - t0 < 30:  # 30 seconds timeout
        # The fastboot device should be found at the same USB path as the recovery device
        usb_dev = get_usb(rom_path, error_on_fail=False)
        if usb_dev is not None and usb_dev.address != rom_devnum:
            if usb_dev.idVendor == KEEMBAY_VID and usb_dev.idProduct == KEEMBAY_PID_FASTBOOT:
                logger.info(f"Found fastboot device at {prettify_usb_addr(rom_path)}!")
                break
        time.sleep(1)
    
    if usb_dev is None or usb_dev.idVendor != KEEMBAY_VID or usb_dev.idProduct != KEEMBAY_PID_FASTBOOT:
        access_error("Keembay fastboot device", f"{prettify_usb_addr(rom_path)}")
    
    # Create a FastbootDevice instance for the fastboot device
    fb_dev = FastbootDevice(usb_dev)
    
    # Run U-Boot firmware if specified
    if "u-boot" in recovery_config["firmware"]:
        logger.info("Running U-Boot firmware")
        run_firmware(fb_dev, "u-boot")
    
    logger.info("Recovery completed successfully")
