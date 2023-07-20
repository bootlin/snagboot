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

import yaml
from snagrecover.utils import cli_error,parse_usb
import logging
logger = logging.getLogger("snagrecover")
import os

default_usb_ids =  {
	# default ROM code USB IDs
	"stm32mp1": (0x0483,0xdf11),
	"sama5":    (0x03eb,0x6124),
	"sunxi":    (0x1f3a,0xefe8),
	"am62x":     (0x0451,0x6165),
	"imx": {
		"imx8qxp": (0x1fc9,0x012f),
		"imx8qm": (0x1fc9,0x0129),
		"imx8dxl": (0x1fc9,0x0147),
		"imx28": (0x15a2,0x004f),
		"imx815": (0x1fc9,0x013e),
		"imx865": ("SDPS",0x1fc9),
		"imx93": (0x1fc9,0x014e),
		"imx7d": (0x15a2,0x0076),
		"imx6q": (0x15a2,0x0054),
		"imx6d": (0x15a2,0x0061),
		"imx6sl": (0x15a2,0x0063),
		"imx6sx": (0x15a2,0x0071),
		"imx6ul": (0x15a2,0x007d),
		"imx6ull": (0x15a2,0x0080),
		"imx6sll": (0x1fc9,0x0128),
		"imx7ulp": (0x1fc9,0x0126),
		"imxrt106x": (0x1fc9,0x0135),
		"imx8mm": (0x1fc9,0x0134),
		"imx8mq": (0x1fc9,0x012b),
	}
}

recovery_config = {} # Global immutable config to be initialized with CLI args

def get_family(soc_model: str) -> str:
        with open(os.path.dirname(__file__) + "/supported_socs.yaml", "r") as file:
                socs = yaml.safe_load(file)
        family = {**socs["tested"], **socs["untested"]}[soc_model]["family"]
        return family

def check_soc_model(soc_model: str):
	with open(os.path.dirname(__file__) + "/supported_socs.yaml", "r") as file:
		socs = yaml.safe_load(file)
	if soc_model not in {**socs["tested"], **socs["untested"]}:
		cli_error(f"unsupported soc model {soc_model}, supported socs: \n" + yaml.dump(socs))
	return None

def init_config(args: list):
	# this is the only time that config.recovery_config should be modified!
	# get soc model
	soc_model = args.soc
	check_soc_model(soc_model)
	recovery_config.update({"soc_model": soc_model})
	soc_family = get_family(soc_model)
	recovery_config.update({"soc_family": soc_family})
	if soc_family != "am335x":
		if args.rom_usb is None:
			if soc_family == "imx":
				recovery_config["rom_usb"] = default_usb_ids["imx"][soc_model]
			else:
				recovery_config["rom_usb"] = default_usb_ids[soc_family]
		else:
			recovery_config["rom_usb"] = parse_usb(args.rom_usb)

	fw_configs = {}
	if args.firmware:
		for fw in args.firmware:
			if type(fw) != dict:
				cli_error("firmware config to CLI did not evaluate to Python3 dict: {fw}")
			fw_configs = {**fw_configs, **fw}
		recovery_config["firmware"] = fw_configs
		if args.firmware_file:
			print("Warning: You passed firmware configuration via files AND direct CLI arguments.")
	if args.firmware_file:
		# get firmware configs
		for path in args.firmware_file:
			with open(path, "r") as file:
				fw_configs = {**fw_configs, **yaml.safe_load(file)}
		if type(fw_configs) != dict:
			cli_error(f"firmware config passed to CLI did not evaluate to dict: {fw_configs}")
		recovery_config["firmware"] = fw_configs

	# store input arguments in config
	recovery_config["args"] = vars(args)
	logger.debug(f"recovery_config:{str(recovery_config)}")

