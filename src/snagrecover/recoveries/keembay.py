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

import logging
from snagrecover.config import recovery_config
from snagrecover.utils import get_usb
from snagrecover.firmware.firmware import run_firmware

logger = logging.getLogger("snagrecover")


def main():
	# USB ENUMERATION
	usb_addr = recovery_config["usb_path"]
	usb_dev = get_usb(usb_addr)

	# Download FIP
	run_firmware(usb_dev, "fip")
