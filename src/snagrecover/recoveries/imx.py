# This file is part of Snagboot
# Copyright (C) 2023 Bootlin
# 
# Written by Romain Gantois <romain.gantois@bootlin.com> in 2023.
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
# Based on NXP mfgtools (https://github.com/nxp-imx/mfgtools):
# Copyright 2018 NXP.
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
# 
# Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
# 
# Redistributions in binary form must reproduce the above copyright notice, this
# list of conditions and the following disclaimer in the documentation and/or
# other materials provided with the distribution.
# 
# Neither the name of the Freescale Semiconductor nor the names of its
# contributors may be used to endorse or promote products derived from this
# software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import hid
import io
import time
import usb
from snagrecover.protocols import memory_ops
from snagrecover.firmware.firmware import run_firmware
from snagrecover.config import recovery_config
import logging
logger = logging.getLogger("snagrecover")

usb_ids = {
"imx8qxp": ["SDPS",0x1fc9,0x012f,0x0002,0xffff],
"imx8qm": ["SDPS",0x1fc9,0x0129,0x0002,0xffff],
"imx8dxl": ["SDPS",0x1fc9,0x0147,0x0000,0xffff],
"imx28": ["SDPS",0x15a2,0x004f,0x0000,0xffff],
"imx815": ["SDPS",0x1fc9,0x013e,0x0000,0xffff],
"imx865": ["SDPS",0x1fc9,0x0146,0x0000,0xffff],
"imx93": ["SDPS",0x1fc9,0x014e,0x0000,0xffff],
"imx7d": ["SDP",0x15a2,0x0076,0x0000,0xffff],
"imx6q": ["SDP",0x15a2,0x0054,0x0000,0xffff],
"imx6d": ["SDP",0x15a2,0x0061,0x0000,0xffff],
"imx6sl": ["SDP",0x15a2,0x0063,0x0000,0xffff],
"imx6sx": ["SDP",0x15a2,0x0071,0x0000,0xffff],
"imx6ul": ["SDP",0x15a2,0x007d,0x0000,0xffff],
"imx6ull": ["SDP",0x15a2,0x0080,0x0000,0xffff],
"imx6sll": ["SDP",0x1fc9,0x0128,0x0000,0xffff],
"imx7ulp": ["SDP",0x1fc9,0x0126,0x0000,0xffff],
"imxrt106x": ["SDP",0x1fc9,0x0135,0x0000,0xffff],
"imx8mm": ["SDP",0x1fc9,0x0134,0x0000,0xffff],
"imx8mq": ["SDP",0x1fc9,0x012b,0x0000,0xffff],
"SPL/1": ["SDPU",0x0525,0xb4a4,0x0000,0x04ff],
"SPL/2": ["SDPU",0x0525,0xb4a4,0x9999,0x9999],
"SPL/3": ["SDPU",0x3016,0x1001,0x0000,0x04ff],
"SPL1/1": ["SDPV",0x0525,0xb4a4,0x0500,0x9998],
"SPL1/2": ["SDPV",0x1fc9,0x0151,0x0500,0x9998],
"SPL1/3": ["SDPV",0x3016,0x100,0x0500,0x9998]
}

###################### main ##################################

def main():
	soc_model = recovery_config["soc_model"]
	protocol = usb_ids[soc_model][0]
	vid = usb_ids[soc_model][1]
	pid = usb_ids[soc_model][2]

	with hid.Device(vid, pid) as dev:
		if protocol == "SDPS":
			run_firmware(dev, "u-boot-sdps")
			return None
		elif "u-boot-with-dcd" in recovery_config["firmware"]:
			run_firmware(dev, "u-boot-with-dcd")
			return None
		elif "SPL" in recovery_config["firmware"]:
			run_firmware(dev, "SPL")
		else:
			run_firmware(dev, "flash-bin", "spl")
		logger.info("SDP command sequence done, closing hid device...")

	#WAIT FOR SPL DEVICE
	print("Waiting for SPL device...")
	t0 = time.time()
	valid_dev = None
	while time.time() - t0 < 5 and (valid_dev is None):
		#Try every possible SPL1 USB config
		for splid in ["SPL1/1","SPL1/2","SPL1/3","SPL/1","SPL/2","SPL/3"]:
			print(f"Trying usb config {splid}")
			protocol = usb_ids[splid][0]
			vid = usb_ids[splid][1]
			pid = usb_ids[splid][2]
			try:
				with hid.Device(vid, pid) as dev:
					bcdVersion = usb.core.find(idVendor=vid, idProduct=pid).bcdDevice
					spl1_cfg = usb_ids[splid]
					if spl1_cfg[3] > bcdVersion or spl1_cfg[4] < bcdVersion:
						raise hid.HIDException("Invalid bcd version")
					valid_dev = [protocol, vid, pid]
			except hid.HIDException:
				continue
			#check protocol using bcdDevice
			if not valid_dev is None:
				print(f"Found HID device with config {splid}")
				break
		time.sleep(1)

	if valid_dev is None:
		raise Exception("Error: No valid SPL HID device found")

	protocol = valid_dev[0]
	with hid.Device(valid_dev[1], valid_dev[2]) as dev:
		#MX8 boot images are more complicated to generate so we allow everything to be
		#packaged in a single blob
		if "imx8" in soc_model:
			if protocol != "SDPV":
				raise Exception("Error: The installed SPL version does not support autofinding U-Boot")
			run_firmware(dev, "flash-bin", "u-boot")
		else:
			run_firmware(dev, "u-boot")

		print("DONE")

