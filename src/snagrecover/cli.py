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
from snagrecover.recoveries.stm32mp1 import main as stm32_recovery
from snagrecover.recoveries.sama5 import main as sama5_recovery
from snagrecover.recoveries.imx import main as imx_recovery
from snagrecover.recoveries.am335 import main as am335_recovery
from snagrecover.recoveries.sunxi import main as sunxi_recovery
from snagrecover.recoveries.am62 import main as am62_recovery
import snagrecover.config as config
import pkg_resources
import yaml
import os
import logging
import ast

def cli():
	template_path = os.path.dirname(__file__) + "/templates"
	template_listing = "\n".join([filename[:-5] for filename in os.listdir(template_path)])
	example = '''Examples:
	python3 recovery -s stm32mp157 -f recovery/templates/stm32mp157f-dk2.yaml -p 0483:df11
	python3 recovery -s stm32mp157 -F "{'tf-a': {'path': 'binaries/tf-a-stm32.bin'}}" -F "{'u-boot': {'path': 'binaries/u-boot.stm32'}}" -p 0483:df11

Templates:
''' + template_listing

	parser = argparse.ArgumentParser(epilog=example, formatter_class=argparse.RawDescriptionHelpFormatter)
	mandatory = parser.add_argument_group("Mandatory")
	mandatory.add_argument("-s", "--soc", help="soc model")
	mandatory.add_argument("-f", "--firmware-file", help="firmware configurations, passed as a yaml file", metavar="\"templates/colibri-imx7d.yaml\"", action="append")
	mandatory.add_argument("-F", "--firmware", help="firmware configurations, formatted as a python3 dict", metavar="\"{'fw1': {'path': '/path/to', 'address': 0x00}}\"", action="append", type=ast.literal_eval)
	optional = parser.add_argument_group("Optional")
	optional.add_argument("--uart", help="use UART for AM335 recovery", metavar="/dev/ttyx")
	optional.add_argument("--baudrate", help="UART baudrate", default=115200)
	optional.add_argument("--netns", help="network namespace for AM335 USB recovery, defaults to 'snagbootnet'", default="snagbootnet")
	optional.add_argument("--loglevel", help="set loglevel", choices=["silent","info","debug"], default="silent")
	optional.add_argument("--logfile", help="set logfile", default="board_recovery.log")
	utilargs = parser.add_argument_group("Utilities")
	utilargs.add_argument("--list-socs", help="list supported socs", action="store_true")
	utilargs.add_argument("--version", help="show version", action="store_true")
	utilargs.add_argument("-t", "--template", help="get an example firmware configuration file", metavar="name")

	args = parser.parse_args()

	#setup logging
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

	#show version
	if args.version:
		version = pkg_resources.require("snagboot")[0].version
		print(f"Snagboot v{version}")
		sys.exit(0)

	#print template
	if args.template:
		path = template_path + "/" + args.template + ".yaml"
		if not os.path.exists(path):
			print(f"Error: no template named {args.template}, please run snagrecover -h for a list of valid templates")
			sys.exit(-1)
		with open(path, "r") as file:
			print(file.read(-1))
		sys.exit(0)

	#show supported socs
	if args.list_socs:
		with open(os.path.dirname(__file__) + "/supported_socs.yaml", "r") as file:
			socs = yaml.safe_load(file)
		print("SoCs that are supported and tested:\n")
		[print(soc) for soc in socs["tested"]]
		print("\nSoCs that are supported but untested:\n")
		[print(soc) for soc in socs["untested"]]
		sys.exit(0)

	if args.soc is None:
		print("Error: Missing command line argument --soc")
		sys.exit(-1)

	if args.firmware is None and (args.firmware_file is None):
		print("Missing command line argument: --firmware or --firmware-file")
		sys.exit(-1)

	#initialize global config
	config.init_config(args)

	#call recovery flow
	soc_model = config.recovery_config["soc_model"]
	soc_family = config.recovery_config["soc_family"]
	print(f"Starting recovery of {soc_model} board")
	logger.info(f"Starting recovery of {soc_model} board")
	if soc_family == "stm32mp1":
		stm32_recovery()
	elif soc_family == "sama5":
		sama5_recovery()
	elif soc_family == "imx":
		imx_recovery()
	elif soc_family == "am335":
		am335_recovery()
	elif soc_family == "sunxi":
		sunxi_recovery()
	elif soc_family == "am62":
		am62_recovery()
	else:
		raise ValueError(f"Unsupported board family {family}")
	print(f"Done recovering {soc_model} board")
	if args.loglevel != "silent":
		print(f"Logs were appended to {args.logfile}")
	logger.info("Done recovering {soc_model} board")

