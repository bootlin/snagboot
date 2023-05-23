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

import usb.core
import usb.util
import time
import logging
logger = logging.getLogger("snagrecover")
from snagrecover import utils

def search_partid(dev: usb.core.Device, partname: str, match_prefix=False) -> int:
	# search for an altsetting associated with a partition name
	cfg = dev.get_active_configuration()
	# note that we're really iterating over multiple altsettings of
	# the same interface here
	partid = None
	intfs = cfg.interfaces()
	for intf in intfs:
		desc = usb.util.get_string(dev, intf.iInterface)
		if (match_prefix and desc.startswith(partname)) or desc == partname:
			partid = intf.bAlternateSetting
	return partid

class DFU():
	DESC_TYPE_DFU = 0x21
	MAN_TOLERANT_MASK = 4

	state_codes = {
		"appIDLE": 0,
		"appDETACH": 1,
		"dfuIDLE": 2,
		"dfuDNLOAD-SYNC": 3,
		"dfuDNBUSY": 4,
		"dfuDNLOAD-IDLE": 5,
		"dfuMANIFEST-SYNC": 6,
		"dfuMANIFEST": 7,
		"dfuMANIFEST-WAIT-RESET": 8,
		"dfuUPLOAD-IDLE": 9,
		"dfuERROR": 10
	}

	status_codes = {
		0x00: "OK",
		0x01: "errTARGET",
		0x02: "errFILE",
		0x03: "errWRITE",
		0x04: "errERASE",
		0x05: "errCHECK_ERASED",
		0x06: "errPROG",
		0x07: "errVERIFY",
		0x08: "errADDRESS",
		0x09: "errNOTDONE",
		0x0A: "errFIRMWARE",
		0x0B: "errVENDOR",
		0x0C: "errUSBR",
		0x0D: "errPOR",
		0x0E: "errUNKNOWN",
		0x0F: "errSTALLEDPKT"
	}

	def __init__(self, dev: usb.core.Device, stm32: bool = True):
		self.dev = dev
		self.stm32 = stm32 # set when dfu is used to recover stm32mp1 boards
		# try to find wTransferSize
		self.transfer_size = 1024
		cfg = dev.get_active_configuration()
		intfs = cfg.interfaces()
		for intf in intfs:
			if len(intf.extra_descriptors) >= 9 and (intf.extra_descriptors[1] == DFU.DESC_TYPE_DFU):
				desc = intf.extra_descriptors
				self.transfer_size = desc[6] * 0x100  + desc[5]
				logger.info(f"Found DFU Functional descriptor: wTransferSize = {self.transfer_size}")


	def check_timeout(timeout: int, t0: int) -> int:
		t1 = round(time.time() * 1000)
		if t1 - t0 < timeout:
			logger.warning("Too soon to send another get_status command")
			while round(time.time() * 1000) - t0 < timeout:
				pass
			t1 = round(time.time() * 1000)
		return round(time.time() * 1000)

	def get_status(self) -> tuple:
		# status = status polltimeout state iString
		status = self.dev.ctrl_transfer(0xa1, 3, wValue=0, wIndex=0, data_or_wLength=6)# DFU_GETSTATUS
		state = status[4]
		timeout = int.from_bytes(bytes(status[1:3]), "little")
		logger.debug(f"DFU state: {state} DFU status: {DFU.status_codes[status[0]]}")
		return (state,timeout)

	def download_and_run(self, blob: bytes, partid: int, offset: int, size: int, show_progress=False) -> bool:
		self.set_partition(partid)
		(state,timeout) = self.get_status()
		t0 = round(time.time() * 1000)
		if state != DFU.state_codes["dfuIDLE"]:
			raise ValueError(f"Incompatible state {state} detected")

		if self.stm32:
			block_index = 2 # wValue 0 and 1 seem to be reserved
		else:
			block_index = 0
		# for other commands (erase, set exec address, etc.)
		bytes_written = 0
		for chunk in utils.dnload_iter(blob[offset:offset + size], self.transfer_size):
			bytes_written += self.dev.ctrl_transfer(0x21, 1, wValue=block_index, wIndex=0, data_or_wLength=chunk)
			progress = int(100 * bytes_written / size)
			if show_progress:
				print(f"\rprogress:{progress}%", end="")
			# make sure to wait enough before sending next get_status
			t0 = DFU.check_timeout(timeout, t0)
			(state,timeout) = self.get_status()
			while state != DFU.state_codes["dfuDNLOAD-IDLE"]:
				# make sure to wait enough before sending next get_status
				t0 = DFU.check_timeout(timeout, t0)
				(state,timeout) = self.get_status()
			block_index += 1
		# send zero-length download command to leave DFU mode and manifest
		# firmware
		bytes_written += self.dev.ctrl_transfer(0x21, 1, wValue=block_index, wIndex=0, data_or_wLength=None)
		t0 = DFU.check_timeout(timeout, t0)
		(state,timeout) = self.get_status()
		while state != DFU.state_codes["dfuIDLE"]:
			t0 = DFU.check_timeout(timeout, t0)
			if state == DFU.state_codes["dfuMANIFEST"]:
				(state,timeout) = self.get_status()
			elif state == DFU.state_codes["dfuMANIFEST-SYNC"]:
				try:
					# this fails on AM625, but is still necessary
					(state,timeout) = self.get_status()
				except usb.core.USBError:
					print("Could not read status after end of manifest phase")
					return True
			elif state == DFU.state_codes["dfuMANIFEST-WAIT-RESET"]:
				self.detach()
				return True
		if show_progress:
			print("")
		logger.info("Done manifesting firmware")
		return True

	def dfu_abort(self):
		self.dev.ctrl_transfer(0x21, 6, wValue=0, wIndex=0, data_or_wLength=None)

	def detach(self, partid: int):
		self.set_partition(partid)
		self.get_status()
		logger.info("Sending DFU_DETACH...")
		self.dev.ctrl_transfer(0xa1, 0, wValue=0x7530, wIndex=0, data_or_wLength=0)
		return None

	def set_partition(self, partid: int):
		self.dev.set_interface_altsetting(interface = 0, alternate_setting = partid)
		return None


	def stm32_get_phase(self) -> int:
		"""
		This returns the next partition to be executed and other
		information I haven't identified yet.
		"""
		partid = search_partid(self.dev, "@virtual", match_prefix=True)
		if partid is None:
				raise Exception("No DFU altsetting found with iInterface='@virtual*'")
		self.set_partition(partid)
		self.get_status()
		# phase = phase_id dnload_addr offset additional_info
		phase = self.dev.ctrl_transfer(0xa1, 2, wValue=0, wIndex=0, data_or_wLength=512)# DFU_UPLOAD
		phase_id = phase[0]
		logger.info(f"Phase id: {phase_id}")
		self.get_status()
		return phase_id

