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

import sys
import argparse
from snagrecover.utils import cli_error
import snagrecover.config as config
import pkg_resources
import yaml
import os
import logging
import ast

def cli():
	udev_path = os.path.dirname(__file__) + "/80-snagboot.rules"
	am335x_script_path = os.path.dirname(__file__) + "/am335x_usb_setup.sh"
	template_path = os.path.dirname(__file__) + "/templates"
	templates = [filename[:-5] for filename in os.listdir(template_path)]
	templates.sort()
	template_listing = "\n".join(templates)
	example = '''Examples:
	snagrecover -s stm32mp15 -f stm32mp15.yaml
	snagrecover -s stm32mp15 -F "{'tf-a': {'path': 'binaries/tf-a-stm32.bin'}}" -F "{'fip': {'path': 'binaries/u-boot.stm32'}}"

Templates:
''' + template_listing

	parser = argparse.ArgumentParser(epilog=example, formatter_class=argparse.RawDescriptionHelpFormatter)
	mandatory = parser.add_argument_group("Mandatory")
	mandatory.add_argument("-s", "--soc", help="soc model")
	mandatory.add_argument("-f", "--firmware-file", help="firmware configurations, passed as a yaml file", metavar="\"templates/colibri-imx7d.yaml\"", action="append")
	mandatory.add_argument("-F", "--firmware", help="firmware configurations, formatted as a python3 dict", metavar="\"{'fw1': {'path': '/path/to', 'address': 0x00}}\"", action="append", type=ast.literal_eval)
	optional = parser.add_argument_group("Optional")
	optional.add_argument("--uart", help="use UART for AM335x recovery", metavar="/dev/ttyx")
	optional.add_argument("--baudrate", help="UART baudrate", default=115200)
	optional.add_argument("--netns", help="network namespace for AM335x USB recovery, defaults to 'snagbootnet'", default="snagbootnet")
	optional.add_argument("--loglevel", help="set loglevel", choices=["silent","info","debug"], default="silent")
	optional.add_argument("--logfile", help="set logfile", default="board_recovery.log")
	optional.add_argument("--rom-usb", help="USB ID used by ROM code", metavar="vid:pid")
	utilargs = parser.add_argument_group("Utilities")
	utilargs.add_argument("--list-socs", help="list supported socs", action="store_true")
	utilargs.add_argument("--version", help="show version", action="store_true")
	utilargs.add_argument("-t", "--template", help="get an example firmware configuration file", metavar="name")
	utilargs.add_argument("--udev", help="get required udev rules for snagrecover", action="store_true")
	utilargs.add_argument("--am335x-setup", help="get setup script for am335x USB recovery", action="store_true")

	args = parser.parse_args()

	# setup logging
	logger = logging.getLogger("snagrecover")
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

	# show version
	if args.version:
		version = pkg_resources.require("snagboot")[0].version
		print(f"Snagboot v{version}")
		sys.exit(0)

	# print template
	if args.template:
		path = template_path + "/" + args.template + ".yaml"
		if not os.path.exists(path):
			cli_error(f"no template named {args.template}, please run snagrecover -h for a list of valid templates")
		with open(path, "r") as file:
			print(file.read(-1))
		sys.exit(0)

	# print udev rules
	if args.udev:
		with open(udev_path, "r") as file:
			print(file.read(-1))
		sys.exit(0)

	# print am335x setup script
	if args.am335x_setup:
		with open(am335x_script_path, "r") as file:
			print(file.read(-1))
		sys.exit(0)

	# show supported socs
	if args.list_socs:
		with open(os.path.dirname(__file__) + "/supported_socs.yaml", "r") as file:
			socs = yaml.safe_load(file)
		print("SoCs that are supported and tested:\n")
		[print(soc) for soc in socs["tested"]]
		print("\nSoCs that are supported but untested:\n")
		[print(soc) for soc in socs["untested"]]
		sys.exit(0)

	if args.soc is None:
		cli_error("missing command line argument --soc")

	if args.firmware is None and (args.firmware_file is None):
		cli_error("missing command line argument: --firmware or --firmware-file")

	# initialize global config
	config.init_config(args)

	# call recovery flow
	soc_model = config.recovery_config["soc_model"]
	soc_family = config.recovery_config["soc_family"]
	print(f"Starting recovery of {soc_model} board")
	logger.info(f"Starting recovery of {soc_model} board")
	if soc_family == "stm32mp1":
		from snagrecover.recoveries.stm32mp1 import main as stm32_recovery
		stm32_recovery()
	elif soc_family == "sama5":
		from snagrecover.recoveries.sama5 import main as sama5_recovery
		sama5_recovery()
	elif soc_family == "imx":
		from snagrecover.recoveries.imx import main as imx_recovery
		imx_recovery()
	elif soc_family == "am335x":
		from snagrecover.recoveries.am335x import main as am335x_recovery
		am335x_recovery()
	elif soc_family == "sunxi":
		from snagrecover.recoveries.sunxi import main as sunxi_recovery
		sunxi_recovery()
	elif soc_family == "am62x":
		from snagrecover.recoveries.am62x import main as am62x_recovery
		am62x_recovery()
	else:
		cli_error(f"unsupported board family {soc_family}")
	print(f"Done recovering {soc_model} board")
	if args.loglevel != "silent":
		print(f"Logs were appended to {args.logfile}")
	logger.info(f"Done recovering {soc_model} board")
