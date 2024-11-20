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

from snagrecover.protocols.hid import HIDDevice
import time
import usb
from snagrecover.firmware.firmware import run_firmware
from snagrecover.config import recovery_config
from snagrecover.utils import access_error, get_usb, prettify_usb_addr
from snagrecover.protocols.imx_sdp import SDPCommand
import logging
logger = logging.getLogger("snagrecover")


# SPL devices that use the SDPV variant of SDP can
# be identified using their bcdVersion
SDPV_MIN_BCDVER = 0x0500
SDPV_MAX_BCDVER = 0x9998

# SoCs that use the SDPS protocol instead of SDP
sdps_socs = [
"imx8qxp",
"imx8qm",
"imx8dxl",
"imx28",
"imx815",
"imx865",
"imx93"
]

# SoCs that use raw bulk endpoints rather than HID
raw_bulk_ep_socs = [
"imx53",
]

def dev_uses_sdpv(usb_dev):
	bcdversion = usb_dev.bcdDevice
	return bcdversion >= SDPV_MIN_BCDVER and bcdversion <= SDPV_MAX_BCDVER

def build_raw_ep_dev(dev: usb.core.Device):
	class Adapter:
		# The protocol code was written to expect a HID device rather
		# than raw USB.
		# This adapter makes it compatible by
		#		- Adding the endpoint numbers to the calls
		#		- Converting read results from an array to bytes
		def __init__(self, dev):
			def is_bulk(ep):
				return usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK
			def is_bulk_in(ep):
				return  is_bulk(ep) and usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN
			def is_bulk_out(ep):
				return is_bulk(ep) and usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT

			cfg = dev.get_active_configuration()
			intf = cfg[(0,0)]
			ep_in = usb.util.find_descriptor(intf, custom_match = is_bulk_in)
			if ep_in is None:
				access_error("USB RAW: cannot find BULK IN endpoint")

			ep_out = usb.util.find_descriptor(intf, custom_match = is_bulk_out)
			if ep_out is None:
				access_error("USB RAW: cannot find BULK OUT endpoint")

			self._dev = dev
			self._read_ep = ep_in.bEndpointAddress
			self._write_ep = ep_out.bEndpointAddress

		def read(self, size, timeout=None):
			return self._dev.read(self._read_ep, size, timeout).tobytes()

		def write(self, data, timeout=None):
			return self._dev.write(self._write_ep, data, timeout)

	return Adapter(dev)

###################### main ##################################

def main():
	soc_model = recovery_config["soc_model"]
	usb_dev = get_usb(recovery_config["usb_path"])

	if soc_model in raw_bulk_ep_socs:
		sdp_cmd = SDPCommand(build_raw_ep_dev(usb_dev))
	else:
		sdp_cmd = SDPCommand(HIDDevice(usb_dev))

	rom_path = (usb_dev.bus, usb_dev.port_numbers)
	rom_devnum = usb_dev.address

	if soc_model in sdps_socs:
		run_firmware(sdp_cmd, "flash-bin", "spl-sdps")
		# On some SoCs (e.g.: i.MX8QM) we can have a second stage based on SPDV
		if soc_model not in ["imx8qm", "imx8qxp"]:
			return None
	elif "u-boot-with-dcd" in recovery_config["firmware"]:
		run_firmware(sdp_cmd, "u-boot-with-dcd")
		return None
	elif "SPL" in recovery_config["firmware"]:
		run_firmware(sdp_cmd, "SPL")
	else:
		run_firmware(sdp_cmd, "flash-bin", "spl")
	logger.info("SDP command sequence done, closing hid device...")
	sdp_cmd.close()

	# WAIT FOR SPL DEVICE
	logger.info("Waiting for SPL device...")
	t0 = time.time()
	while time.time() - t0 < 5:
		# The SPL device should be found at the same USB path as the ROM device
		usb_dev = get_usb(rom_path, error_on_fail=False)
		if usb_dev is not None and usb_dev.address != rom_devnum:
			logger.info(f"Found USB device at {prettify_usb_addr(rom_path)} for SPL stage!")
			break

		time.sleep(1)

	if usb_dev is None:
		access_error("SPL USB HID", f"{prettify_usb_addr(rom_path)}")

	sdp_cmd = SDPCommand(HIDDevice(usb_dev))
	# MX8 boot images are more complicated to generate so we allow everything to be
	# packaged in a single blob
	if "imx8" in soc_model:
		if not dev_uses_sdpv(usb_dev):
			raise Exception("Error: The installed SPL version does not support autofinding U-Boot")
		run_firmware(sdp_cmd, "flash-bin", "u-boot")
	else:
		run_firmware(sdp_cmd, "u-boot")

	sdp_cmd.close()
	logger.info("DONE")

