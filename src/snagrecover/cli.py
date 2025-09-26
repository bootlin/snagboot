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
from snagrecover import __version__
from snagrecover.utils import cli_error, get_recovery, get_supported_socs
import snagrecover.config as config
import logging
import ast
import importlib.resources


def cli():
	templates = {}

	for file in (
		importlib.resources.files("snagrecover").joinpath("templates").iterdir()
	):
		template_name = file.name[:-5]
		templates[template_name] = file

	template_listing = "\n".join(sorted(templates.keys()))
	example = (
		"""Examples:
	snagrecover -s stm32mp15 -f stm32mp15.yaml
	snagrecover -s stm32mp15 -F "{'tf-a': {'path': 'binaries/tf-a-stm32.bin'}}" -F "{'fip': {'path': 'binaries/u-boot.stm32'}}"

Templates:
"""
		+ template_listing
	)

	parser = argparse.ArgumentParser(
		epilog=example, formatter_class=argparse.RawDescriptionHelpFormatter
	)
	mandatory = parser.add_argument_group("Mandatory")
	mandatory.add_argument("-s", "--soc", help="soc model")
	mandatory.add_argument(
		"-f",
		"--firmware-file",
		help="firmware configurations, passed as a yaml file",
		metavar='"templates/colibri-imx7d.yaml"',
		action="append",
	)
	mandatory.add_argument(
		"-F",
		"--firmware",
		help="firmware configurations, formatted as a python3 dict",
		metavar="\"{'fw1': {'path': '/path/to', 'address': 0x00}}\"",
		action="append",
		type=ast.literal_eval,
	)
	optional = parser.add_argument_group("Optional")
	optional.add_argument(
		"--uart", help="use UART for AM335x recovery", metavar="/dev/ttyx"
	)
	optional.add_argument("--baudrate", help="UART baudrate", default=115200)
	optional.add_argument(
		"--netns",
		help="network namespace for AM335x USB recovery, defaults to 'snagbootnet'",
		default="snagbootnet",
	)
	optional.add_argument(
		"--loglevel",
		help="set loglevel",
		choices=["silent", "info", "debug"],
		default="silent",
	)
	optional.add_argument("--logfile", help="set logfile", default="board_recovery.log")
	optional.add_argument("--rom-usb", help="legacy, please use --usb-path")
	optional.add_argument(
		"--usb-path",
		help="address of recovery USB device",
		metavar="vid:pid|bus-port1.port2.[...]",
	)
	utilargs = parser.add_argument_group("Utilities")
	utilargs.add_argument(
		"--list-socs", help="list supported socs", action="store_true"
	)
	utilargs.add_argument("--version", help="show version", action="store_true")
	utilargs.add_argument(
		"-t",
		"--template",
		help="get an example firmware configuration file",
		metavar="name",
	)
	utilargs.add_argument(
		"--udev", help="get required udev rules for snagrecover", action="store_true"
	)
	utilargs.add_argument(
		"--am335x-setup",
		help="get setup script for am335x USB recovery",
		action="store_true",
	)

	args = parser.parse_args()

	# setup logging
	logger = logging.getLogger("snagrecover")
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
			log_handler.setLevel(logging.DEBUG)
		elif args.loglevel == "info":
			log_handler.setLevel(logging.INFO)
		logger.addHandler(log_handler)

	# show version
	if args.version:
		logger.info(f"Snagboot v{__version__}")
		sys.exit(0)

	# print template
	if args.template:
		if args.template not in templates:
			cli_error(
				f"no template named {args.template}, please run snagrecover -h for a list of valid templates"
			)

		with templates[args.template].open("r") as file:
			print(file.read(-1))

		sys.exit(0)

	# print udev rules
	if args.udev:
		print(importlib.resources.read_text("snagrecover", "50-snagboot.rules"))
		sys.exit(0)

	# print am335x setup script
	if args.am335x_setup:
		print(importlib.resources.read_text("snagrecover", "am335x_usb_setup.sh"))
		sys.exit(0)

	# show supported socs
	if args.list_socs:
		socs = get_supported_socs()
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
	logger.info(f"Starting recovery of {soc_model} board")

	recovery = get_recovery(soc_family)
	recovery()

	logger.info(f"Done recovering {soc_model} board")
	if args.loglevel != "silent":
		logger.info(f"Logs were appended to {args.logfile}")


if __name__ == "__main__":
	cli()
