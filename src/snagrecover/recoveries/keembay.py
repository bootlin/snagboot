# This file is part of Snagboot
# Copyright (C) 2025 Bootlin
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

import time
import logging
from snagrecover.config import recovery_config
from snagrecover.utils import access_error, get_usb, prettify_usb_addr
from snagrecover.firmware.firmware import run_firmware
from snagrecover.protocols.fastboot import Fastboot

logger = logging.getLogger("snagrecover")

USB_TIMEOUT = 30

# Intel Keembay USB VID:PID (fastboot mode)
KEEMBAY_VID = 0x8087
KEEMBAY_PID_FASTBOOT = 0xda00

def main():
    recovery_state=False

    soc_model = recovery_config["soc_model"]
    # USB ENUMERATION
    usb_addr = recovery_config["usb_path"]
    usb_dev = get_usb(usb_addr)
    cfg = usb_dev.get_active_configuration()
    logger.debug("USB config:")
    for line in str(cfg).splitlines():
        logger.debug(line)
    logger.debug("End of USB config:")

    # Flash the FIP using fastboot
    fip_path = recovery_config["firmware"]["fip"]["path"]
    logger.info(f"Flashing FIP from {fip_path}")
    fb_dev = Fastboot(usb_dev)
    fb_dev.download(fip_path)
    logger.info("FIP flashed successfully")
    
    logger.info("Waiting for device to reboot into fastboot mode...")
    rom_path = (usb_dev.bus, usb_dev.port_numbers)
    rom_devnum = usb_dev.address
    
    # The fastboot device should be found at the same USB path as the recovery device
    time.sleep(10)
    usb_dev = get_usb(rom_path, error_on_fail=False)

    if usb_dev is not None and usb_dev.address != rom_devnum:
        cfg = usb_dev.get_active_configuration()
        if usb_dev.idVendor == KEEMBAY_VID and usb_dev.idProduct == KEEMBAY_PID_FASTBOOT:
            logger.info(f"Found fastboot device at {prettify_usb_addr(rom_path)}!")
            recovery_state=True

    return recovery_state
