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

from snagrecover.protocols import dfu
import logging
logger = logging.getLogger("snagflash")
from snagflash.utils import int_arg
import usb

def dfu_cli(args):
	if args.dfu_config is None:
		raise Exception("Missing command line argument --dfu-config")
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
	for dfu_config in args.dfu_config:
		(altsetting,sep,path) = dfu_config.partition(":")
		if "," in altsetting:
			(altsetting,sep,size) = altsetting.partition(",")
			size = int_arg(size)
		else:
			size = None
		altsetting = int(altsetting)
		with open(path, "rb") as file:
			blob = file.read(-1)
		if size is None:
			size = len(blob)
		logger.debug(f"DFU config altsetting:{altsetting} size:0x{size:x} path:{path}")
		dfu_cmd = dfu.DFU(dev, stm32=False) 
		dfu_cmd.get_status()
		dfu_cmd.download_and_run(blob, altsetting, 0, size, show_progress=True)
		dfu_cmd.get_status()
	dfu_cmd.detach(altsetting)



