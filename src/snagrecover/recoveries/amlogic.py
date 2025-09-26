# This file is part of Snagboot
# Copyright (C) 2025 Bootlin
#
# Written by François Foltete <francois.foltete@bootlin.com> in 2025.
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
#
# Based on pyamlboot (https://github.com/superna9999/pyamlboot):
# MIT License

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import logging

logger = logging.getLogger("snagrecover")
from time import sleep
from snagrecover.firmware.firmware import run_firmware
from snagrecover.utils import get_usb
from snagrecover.config import recovery_config


def main():
	# USB ENUMERATION
	usb_path = recovery_config["usb_path"]
	dev = get_usb(usb_path)

	protocol_1_socs = [
		# G12A
		"s905d2",
		"s905y2",
		"s905x2",
		# G12B
		"a311d",
		"s922x",
		# SM1
		"s905x3",
		"s905d3",
	]
	protcol_2_socs = [
		# GXL
		"s905d",
		"s905x",
		"s905w",
		"s905l",
		"s905m2",
		"s805x",
		"s805y",
		# GXM
		"s912",
		# GXBB
		"s905",
		"s905h",
		"s905m",
		# AXG
		"a113x",
		"a113d",
	]

	if recovery_config["soc_model"] in protocol_1_socs:
		logger.debug("Starting recovery process using protocol for G12x and SM1 SoCs")
		# Recovery first downloads BL2, then communicates with it to download U-Boot in chunks.
		run_firmware(dev, "u-boot-fip", "BL2")

		logger.info("Waiting for BL2 to start...")
		sleep(2)

		run_firmware(dev, "u-boot-fip", "U-Boot")

	elif recovery_config["soc_model"] in protcol_2_socs:
		logger.debug("Starting recovery process for GXx and AXG SoCs")
		run_firmware(dev, "bl2")
		run_firmware(dev, "u-boot")
	else:
		err_msg = f"Unable to find corresponding AMLogic recovery protocol for {recovery_config['soc_model']}"
		logger.critical(err_msg)
		raise ValueError(err_msg)
