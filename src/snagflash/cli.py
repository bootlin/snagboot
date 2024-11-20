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
from snagrecover import __version__
from snagflash.dfu import dfu_cli
from snagflash.fastboot import fastboot
from snagrecover.utils import cli_error
import platform
import logging
import sys

if platform.system() == "Linux":
	from snagflash.ums import ums
	protocols = ["dfu", "ums", "fastboot"]
else:
	protocols = ["dfu", "fastboot"]

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
	common.add_argument("-P", "--protocol", help="Protocol to use for flashing", choices=protocols)
	common.add_argument("-p", "--port", help="USB device address for DFU and Fastboot commands", metavar="vid:pid|bus-port1.port2.[...]")
	common.add_argument("--timeout", help="USB timeout, sometimes increasing this is necessary when downloading large files", default=60000)
	dfuargs = parser.add_argument_group("DFU")
	dfuargs.add_argument("-D", "--dfu-config", help="The altsetting and path of a file to download to the board. in DFU mode", action="append", metavar="altsetting:path")
	dfuargs.add_argument("--dfu-keep", help="Avoid detaching DFU mode after download and keep the mode active", action="store_true")
	dfuargs.add_argument("--dfu-detach", help="Only request detaching DFU mode", action="store_true")
	dfuargs.add_argument("--dfu-reset", help="Reset USB device after download and reboot the board", action="store_true")
	fbargs = parser.add_argument_group("Fastboot")
	fbargs.add_argument("-f", "--fastboot-cmd", help="A fastboot command.", action="append", metavar="cmd:args")
	fbargs.add_argument("-i", "--interactive", help="Start interactive mode", action="store_true")
	fbargs.add_argument("-I", "--interactive-cmdfile", help="Read interactive mode commands from file")
	if platform.system() == "Linux":
		umsargs = parser.add_argument_group("UMS")
		umsargs.add_argument("-s", "--src", help="source file for UMS transfer")
		umsargs.add_argument("-d", "--dest", help="mounted transfer: set destination file name")
		umsargs.add_argument("-b", "--blockdev", help="raw transfer: set destination block device", metavar="device")

	args = parser.parse_args()

	# show version
	if args.version:
		print(f"Snagboot v{__version__}")
		sys.exit(0)

	# setup logging
	logger = logging.getLogger('snagflash')
	logger.setLevel(logging.DEBUG)
	log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

	stdout_handler = logging.StreamHandler(sys.stdout)
	stdout_handler.setLevel(logging.INFO)
	stdout_handler.setFormatter(log_formatter)
	logger.addHandler(stdout_handler)

	if args.loglevel != "silent":
		log_handler = logging.FileHandler(args.logfile, encoding="utf-8")
		log_handler.setFormatter(log_formatter)
		if args.loglevel == "debug":
			logger.setLevel(logging.DEBUG)
		elif args.loglevel == "info":
			logger.setLevel(logging.INFO)
		logger.addHandler(log_handler)

	# make sure we don't log into the recovery log when importing its modules
	recovery_logger = logging.getLogger('snagrecover')
	recovery_logger.parent = logger

	logger.info("Running snagflash using protocol {args.protocol}")
	if args.protocol == "dfu":
		dfu_cli(args)
	elif args.protocol == "ums":
		if args.src is None or (args.blockdev is None and args.dest is None):
			cli_error("missing an UMS config!")
		ums(args)
	elif args.protocol == "fastboot":
		if args.fastboot_cmd is None:
			args.fastboot_cmd = []
		fastboot(args)
	else:
		cli_error(f"unrecognized protocol {args.protocol}")

