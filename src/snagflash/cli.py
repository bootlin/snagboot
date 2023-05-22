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

import argparse
from snagflash.dfu import dfu_cli
from snagflash.ums import ums
from snagflash.fastboot import fastboot
from snagflash.utils import cli_error
import logging
import pkg_resources
import sys

def cli():
	example = '''Examples:
	# U-Boot: fastboot usb 0
	snagflash -P fastboot -p 0483:0afb -f download:boot.img -f flash:0:1 -f boot
	# U-Boot: ums 0 mmc 0
	snagflash -P ums -s binaries/u-boot.stm32 -b /dev/sdb1
	snagflash -P ums -s binaries/u-boot.stm32 -d /mnt/u-boot.stm32
	# U-Boot: setenv dfu_alt_info "mmc=uboot part 0 1"
	# U-Boot: dfu 0 mmc 0
	snagflash -P dfu -p 0483:df11 -D 0:binaries/u-boot.stm32
	'''
	parser = argparse.ArgumentParser(epilog=example, formatter_class=argparse.RawDescriptionHelpFormatter)
	common = parser.add_argument_group("Common")
	common.add_argument("--loglevel", help="set loglevel", choices=["silent","info","debug"], default="silent")
	common.add_argument("--logfile", help="set logfile", default="board_flashing.log")
	common.add_argument("--version", help="show version", action="store_true")
	common.add_argument("-P", "--protocol", help="Protocol to use for flashing", choices=["dfu","ums","fastboot"])
	common.add_argument("-p", "--port", help="USB device address for DFU and Fastboot commands", metavar="vid:pid")
	common.add_argument("--timeout", help="USB timeout, sometimes increasing this is necessary when downloading large files", default=60000)
	dfuargs = parser.add_argument_group("DFU")
	dfuargs.add_argument("-D", "--dfu-config", help="The altsetting and path of a file to download to the board. in DFU mode", action="append", metavar="altsetting:path")
	fbargs = parser.add_argument_group("Fastboot")
	fbargs.add_argument("-f", "--fastboot-cmd", help="A fastboot command.", action="append", metavar="cmd:args")
	umsargs = parser.add_argument_group("UMS")
	umsargs.add_argument("-s", "--src", help="source file for UMS transfer")
	umsargs.add_argument("-d", "--dest", help="mounted transfer: set destination file name")
	umsargs.add_argument("-b", "--blockdev", help="raw transfer: set destination block device", metavar="device")
	umsargs.add_argument("--size", help="raw transfer: transfer size")
	args = parser.parse_args()

	# show version
	if args.version:
		version = pkg_resources.require("snagboot")[0].version
		print(f"Snagboot v{version}")
		sys.exit(0)

	# setup logging
	logger = logging.getLogger('snagflash')
	if args.loglevel == "silent":
		logger.addHandler(logging.NullHandler())
	else:
		log_handler = logging.FileHandler(args.logfile, encoding="utf-8")
		log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
		log_handler.setFormatter(log_formatter)
		logger.addHandler(log_handler)
		if args.loglevel == "debug":
			logger.setLevel(logging.DEBUG)
		elif args.loglevel == "info":
			logger.addHandler(log_handler)
			logger.setLevel(logging.INFO)
	# make sure we don't log into the recovery log when importing its modules
	recovery_logger = logging.getLogger('snagrecover')
	recovery_logger.parent = logger

	logger.info("Running snagflash using protocol {args.protocol}")
	if args.protocol == "dfu":
		if args.dfu_config is None:
			cli_error("missing at least one DFU config!")
		dfu_cli(args)
	elif args.protocol == "ums":
		if args.src is None or (args.blockdev is None and args.dest is None):
			cli_error("missing an UMS config!")
		ums(args)
	elif args.protocol == "fastboot":
		if args.fastboot_cmd is None:
			cli_error("missing at least one fastboot command!")
		fastboot(args)
	else:
		cli_error(f"unrecognized protocol {args.protocol}")

