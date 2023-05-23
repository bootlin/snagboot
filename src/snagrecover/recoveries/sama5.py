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

import serial
import os.path
import time

from snagrecover.protocols import sambamon
from snagrecover.protocols import memory_ops
from snagrecover.firmware.firmware import run_firmware
from snagrecover.config import recovery_config
from snagrecover.utils import access_error,get_usb
import logging

logger = logging.getLogger("snagrecover")

aximx_remap = {
		"sama5d2": 0x600000,
		"sama5d3": 0x800000,
		"sama5d4": 0x700000,
}
SFR_L2CC_HRAMC = 0xf8030058

SERIAL_PORT_TIMEOUT = 5

# chipid config values are from Microchip SAM-BA v3.7 for Linux
chipid_configs = {
    "sama5d2": {
            "CIDR_REG":      0xfc069000,
            "CIDR_MASK": 0xffffffe0,
            "CIDR_VAL":      0x8a5c08c0
    },
    "sama5d3": {
            "CIDR_REG":      0xffffee40,
            "CIDR_MASK": 0xfffffffe,
            "CIDR_VAL":      0x8a5c07c2,
            "EXID_REG": 0xffffee44,
            "EXID_VAL": [
                    0x00444300,
                    0x00414300,
                    0x00414301,
                    0x00584300,
                    0x00004301
            ]
    },
    "sama5d4": {
            "CIDR_REG":      0xfc069040,
            "CIDR_MASK": 0xffffffe0,
            "CIDR_VAL":      0x8a5c07c0
    }
}

def check_id(memops: memory_ops.MemoryOps) -> bool:
    soc_model = recovery_config["soc_model"]
    cfg = chipid_configs[soc_model]
    cidr = memops.read32(cfg["CIDR_REG"])
    chip_id = cidr & cfg["CIDR_MASK"]
    check = chip_id == cfg["CIDR_VAL"]
    if soc_model == "sama5d3":
            exid = memops.read32(cfg["EXID_REG"])
            check &= exid in cfg["EXID_VAL"]
    return check

def main():
	# CONNECT TO SAM-BA MONITOR
	print("Connecting to SAM-BA monitor...")
	soc_model = recovery_config["soc_model"]
	usb_vid = recovery_config["rom_usb"][0]
	usb_pid = recovery_config["rom_usb"][1]
	dev = get_usb(usb_vid, usb_pid)
	dev.reset()# SAM-BA monitor needs a reset sometimes

	port_path = f"/dev/serial/by-id/usb-{usb_vid:04x}_{usb_pid:04x}-if00"
	t0 = time.time()
	while not os.path.exists(port_path):
		if time.time() - t0 > SERIAL_PORT_TIMEOUT:
			access_error("serial port", f"{port_path}")

	with serial.Serial(os.path.realpath(port_path), baudrate=115200, timeout=5, write_timeout=5) as port:
		monitor = sambamon.SambaMon(port)
		memops = memory_ops.MemoryOps(monitor)
		logger.info("SAM-BA Monitor version string: " + monitor.get_version())
		print("Done connecting")

		# CHECK BOARD ID
		print("Checking chip id...")
		if not check_id(memops):
			raise ValueError("Error: Invalid CIDR or EXID, chip model not recognized, please check your soc model argument")

		print("Done checking")
		if soc_model == "sama5d2":
			# reconfigure L2 cache as SRAM
			memops.write32(SFR_L2CC_HRAMC, 0x00)

		# INITIALIZE CLOCK TREE
		print("Initializing clock tree...")
		run_firmware(port, "lowlevel")
		print("Done initializing clock tree")


		# INITIALIZE EXTRAM
		print("Initializing external RAM...")
		run_firmware(port, "extram")
		print("Done initializing RAM")

		# REMAP ROM ADDRESSES
		memops.write32(aximx_remap[soc_model], 0x01)# remap ROM addresses to SRAM0

		# DOWNLOAD U-BOOT
		print("Installing U-Boot...")
		run_firmware(port, "u-boot")
		print("Done!")
