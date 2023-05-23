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

from snagrecover.protocols import fastboot as fb
from snagflash.utils import get_usb
import sys
import logging
logger = logging.getLogger("snagflash")

def fastboot(args):
	if (args.port is None) or (":" not in args.port):
		print("Error: Missing command line argument --port [vid:pid]")
		sys.exit(-1)
	dev_addr = args.port.split(":")
	vid  = int(dev_addr[0], 16)
	pid = int(dev_addr[1], 16)
	dev = get_usb(vid, pid)
	dev.default_timeout = int(args.timeout)
	fast = fb.Fastboot(dev)
	# this is mostly there to dodge a linter error
	logger.debug(f"Fastboot object: eps {fast.ep_in} {fast.ep_out} packet size {fast.max_size}")
	for cmd in args.fastboot_cmd:
		if ":" in cmd:
			(cmd, sep, args) = cmd.partition(":")
		else:
			args = None
		cmd = cmd.translate({ord("-"): ord("_")})
		print(f"Sending command {cmd} with args {args}")
		if args is None:
			eval(f"fast.{cmd}()")
		else:
			eval(f"fast.{cmd}(args)")
	print("Done")

