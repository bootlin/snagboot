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

import usb
from snagrecover.protocols import fastboot as fb


def fastboot(args):
	if (args.port is None) or (":" not in args.port):
		print("Error: Missing command line argument --port [vid:pid]")
		sys.exit(-1)
	dev_addr = args.port.split(":")
	vendor_id  = int(dev_addr[0], 16)
	product_id = int(dev_addr[1], 16)
	dev = usb.core.find(idVendor=vendor_id, idProduct=product_id)
	if dev is None:
		raise ValueError('USB device not found')
	dev.default_timeout = int(args.timeout)
	fast = fb.Fastboot(dev)
	for cmd in args.fastboot_cmd:
		if ":" in cmd:
			(cmd, sep, args) = cmd.partition(":")
		else:
			args = None 
		cmd = cmd.translate({ord("-"): ord("_")})
		if args is None:  
			eval(f"fast.{cmd}()")
		else:
			eval(f"fast.{cmd}(args)")

