# This file is part of Snagboot
# Copyright (C) 2025 Luxonis
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

logger = logging.getLogger("snagrecover")

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

    # Download FIP
    run_firmware(usb_dev, "fip")
