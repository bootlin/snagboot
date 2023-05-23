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

import logging
logger = logging.getLogger("snagrecover")
from snagrecover.firmware import samba_applet
from snagrecover.protocols import sambamon
from snagrecover.protocols import memory_ops
from snagrecover.config import recovery_config

def sama5_run(port, fw_name: str, fw_blob: bytes):
	backend = sambamon.SambaMon(port)
	memops = memory_ops.MemoryOps(backend)
	if fw_name == "extram":
		print("Initializing external RAM...")
		applet = samba_applet.ExtramApplet(memops, fw_blob)
		if applet is None:
			raise ValueError("Error: unsupported board model")
		extram_status = applet.run()
		if extram_status != "APPLET_SUCCESS":
			raise ValueError("Error: extram applet returned error status: " + extram_status)
		print("Done")
	elif fw_name == "lowlevel":
		print("Initializing clock tree...")
		applet = samba_applet.LowlevelApplet(memops, fw_blob)
		lowlevel_status = applet.run()
		if lowlevel_status != "APPLET_SUCCESS":
			raise ValueError("Error: lowlevel applet returned error status: " + lowlevel_status)
		print("Done")
	elif fw_name == "u-boot":
		addr = recovery_config["firmware"]["u-boot"]["address"]
		print("Downloading file...")
		memops.write_blob(fw_blob, addr, offset=0, size=len(fw_blob))
		print("Done")
		print("Jumping to U-Boot...")
		memops.jump(addr)
	else:
		raise ValueError(f"Error: Unsupported firmware {fw_name}")
	return None

