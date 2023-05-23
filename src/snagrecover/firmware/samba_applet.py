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
# Based on atmel-software-package (https://github.com/atmelcorp/atmel-software-package):
#
# Copyright (c) 2015-2017, Atmel Corporation All rights reserved.
# ---------------------------------------------------------------
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# - Redistributions of source code must retain the above copyright notice,
# this list of conditions and the disclaimer below.
#
# - Atmel's name may not be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# DISCLAIMER: THIS SOFTWARE IS PROVIDED BY ATMEL "AS IS" AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT ARE
# DISCLAIMED. IN NO EVENT SHALL ATMEL BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import logging
logger = logging.getLogger("snagrecover")
from snagrecover.protocols import memory_ops
from snagrecover.config import recovery_config
from snagrecover.utils import cli_error

class Applet():
	# constants defined in atmel-software-package/samba_applets
	APPLET_CMD_INITIALIZE = 0
	COMM_TYPE_USB = 0

	trace_levels = {
		"TRACE_LEVEL_DEBUG"	  :	  5,
		"TRACE_LEVEL_INFO"	  :	  4,
		"TRACE_LEVEL_WARNING" :	  3,
		"TRACE_LEVEL_ERROR"	  :	  2,
		"TRACE_LEVEL_FATAL"	  :	  1,
		"TRACE_LEVEL_SILENT"  :	  0
	}

	status_codes = {
			0x00: "APPLET_SUCCESS",
			0x01: "APPLET_DEV_UNKNOWN",
			0x02: "APPLET_WRITE_FAIL",
			0x03: "APPLET_READ_FAIL",
			0x04: "APPLET_PROTECT_FAIL",
			0x05: "APPLET_UNPROTECT_FAIL",
			0x06: "APPLET_ERASE_FAIL",
			0x07: "APPLET_NO_DEV",
			0x08: "APPLET_ALIGN_ERROR",
			0x09: "APPLET_BAD_BLOCK",
			0x0a: "APPLET_PMECC_CONFIG",
			0x0f: "APPLET_FAIL"
	}

	def __init__(self, memops: memory_ops.MemoryOps, fw_blob: bytes):
		self.memops = memops
		self.image = fw_blob

		# struct used to configure sam-ba applets, with default params for extram
		self.mailbox = {
			"cmd": Applet.APPLET_CMD_INITIALIZE,
			# not a valid status code, probably used to check if
			# applet really wrote a return status
			"status": 0xffffffff,
			"com_type": Applet.COMM_TYPE_USB,
			"trace_lvl": Applet.trace_levels["TRACE_LEVEL_DEBUG"],
			"console_instance": None,
			"console_ioset": None,
			"applet_params": None,
		}

		soc_model = recovery_config["soc_model"]
		if soc_model == "sama5d2":
			self.address = 0x220000
		elif soc_model == "sama5d3":
			self.address = 0x300000
		elif soc_model == "sama5d4":
			self.address = 0x200000

	def get_status(self) -> str:
		return Applet.status_codes[self.memops.read32(self.address + 8)]

	def configure(self) -> str:
		# send command and parameters to applet before running it
		logger.info("Starting configuring applet")
		offset = 0
		for param in ["cmd", "status", "com_type", "trace_lvl",\
			"console_instance", "console_ioset"]:
			self.memops.write32(self.address + 4 + offset, self.mailbox[param])
			offset += 4

		for applet_param in self.mailbox["applet_params"].keys():
			self.memops.write32(self.address + 4 + offset,\
				self.mailbox["applet_params"][applet_param])
			offset += 4

	def run(self) -> str:
		self.memops.write_blob(self.image, self.address, offset=0, size=len(self.image))
		self.configure()
		self.memops.jump(self.address)
		return self.get_status()


class LowlevelApplet(Applet):

	def __init__(self, memops:memory_ops.MemoryOps, fw_blob: bytes):
		Applet.__init__(self, memops, fw_blob)

		self.mailbox["console_instance"] = recovery_config["firmware"]["lowlevel"]["console_instance"]
		self.mailbox["console_ioset"] = recovery_config["firmware"]["lowlevel"]["console_ioset"]
		self.mailbox["applet_params"] = {
				"preset": 0,# this parameter seems to be irrelevant for sama5d
		}

class ExtramApplet(Applet):

	ram_presets = {
		"DDR2_MT47H128M8:Preset 0 (4 x MT47H128M8)": 0,
		"DDR2_MT47H64M16:Preset 1 (1 x MT47H64M16)": 1,
		"DDR2_MT47H64M16:Preset 17 (2 x MT47H64M16)": 17,
		"DDR2_MT47H128M16:Preset 2 (2 x MT47H128M16)": 2,
		"DDR2_MT47H128M16:Preset 18 (1 x MT47H128M16)": 18,
		"LPDDR2_MT42L128M16:Preset 3 (2 x MT42L128M16)": 3,
		"DDR3_MT41K128M16:Preset 4 (2 x MT41K128M16)": 4,
		"DDR3_MT41K128M16:Preset 11 (1 x MT41K128M16)": 11,
		"LPDDR3_EDF8164A3MA:Preset 5 (EDF8164A3MA)": 5,
		"SDRAM_IS42S16100E:Preset 6 (IS42S16100E)": 6,
		"SDRAM_W981216BH:Preset 7 (W981216BH)": 7,
		"DDR2_W971GG6SB:Preset 8 (W971GG6SB)": 8,
		"DDR2_W972GG6KB:Preset 9 (W972GG6KB)": 9,
		"DDR2_W972GG6KB:Preset 12 (W972GG6KB_16)": 12,
		"SDRAM_AS4C16M16SA:Preset 10 (AS4C16M16SA)": 10,
		"LPDDR2_AD220032D:Preset 13 (AD220032D)": 13,
		"LPDDR2_AD210032D:Preset 14 (AD210032D)": 14,
		"DDR2_W9712G6KB:Preset 15 (W9712G6KB)": 15,
		"DDR2_W9751G6KB:Preset 16 (W9751G6KB)": 16
	}

	def __init__(self, memops: memory_ops.MemoryOps, fw_blob: bytes):
		Applet.__init__(self, memops, fw_blob)

		self.mailbox["applet_params"] = {
				"mode": 0,# extram only has one mode
				"preset": None,
		}

		self.mailbox["console_instance"] = recovery_config["firmware"]["extram"]["console_instance"]
		self.mailbox["console_ioset"] = recovery_config["firmware"]["extram"]["console_ioset"]
		self.mailbox["applet_params"]["preset"] = ExtramApplet.ram_presets.get(recovery_config["firmware"]["extram"]["preset"], None)
		if self.mailbox["applet_params"]["preset"] is None:
			cli_error("Unsupported preset for extram applet")

