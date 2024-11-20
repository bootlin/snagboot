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
from snagrecover.utils import cli_error, usb_addr_to_path, get_family, access_error
import logging
logger = logging.getLogger("snagrecover")
import os

default_usb_ids =  {
	# default ROM code USB IDs
	"stm32mp1": "0483:df11",
	"sama5":    "03eb:6124",
	"sunxi":    "1f3a:efe8",
	"am6x":     "0451:6165",
	"imx": {
		"imx8qxp": "1fc9:012f",
		"imx8qm": "1fc9:0129",
		"imx8dxl": "1fc9:0147",
		"imx28": "15a2:004f",
		"imx815": "1fc9:013e",
		"imx865": "1fc9:0146",
		"imx93": "1fc9:014e",
		"imx7d": "15a2:0076",
		"imx6q": "15a2:0054",
		"imx6d": "15a2:0061",
		"imx6sl": "15a2:0063",
		"imx6sx": "15a2:0071",
		"imx6ul": "15a2:007d",
		"imx6ull": "15a2:0080",
		"imx6sll": "1fc9:0128",
		"imx7ulp": "1fc9:0126",
		"imxrt106x": "1fc9:0135",
		"imx8mm": "1fc9:0134",
		"imx8mq": "1fc9:012b",
		"imx53" : "15a2:004e",
	}
}

recovery_config = {} # Global immutable config to be initialized with CLI args

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

	if args.rom_usb is not None and args.usb_path is None:
		args.usb_path = args.rom_usb

	if soc_family != "am335x":
		if args.usb_path is None:
			if soc_family == "imx":
				usb_ids = default_usb_ids["imx"][soc_model]
			else:
				usb_ids = default_usb_ids[soc_family]

			recovery_config["usb_path"] = usb_addr_to_path(usb_ids)

			if recovery_config["usb_path"] is None:
				access_error("USB", usb_ids)

		else:
			recovery_config["usb_path"] = usb_addr_to_path(args.usb_path)
			if recovery_config["usb_path"] is None:
				access_error("USB", args.usb_path)

	fw_configs = {}
	if args.firmware:
		for fw in args.firmware:
			if not isinstance(fw, dict):
				cli_error("firmware config to CLI did not evaluate to Python3 dict: {fw}")
			fw_configs = {**fw_configs, **fw}
		recovery_config["firmware"] = fw_configs
		if args.firmware_file:
			logger.warning("You passed firmware configuration via files AND direct CLI arguments!")
	if args.firmware_file:
		# get firmware configs
		for path in args.firmware_file:
			with open(path, "r") as file:
				fw_configs = {**fw_configs, **yaml.safe_load(file)}
		if not isinstance(fw_configs, dict):
			cli_error(f"firmware config passed to CLI did not evaluate to dict: {fw_configs}")
		recovery_config["firmware"] = fw_configs

	# store input arguments in config
	recovery_config["args"] = vars(args)
	logger.debug(f"recovery_config:{str(recovery_config)}")

