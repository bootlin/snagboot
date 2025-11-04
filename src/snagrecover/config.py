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

import os
import yaml
from snagrecover.utils import (
	cli_error,
	usb_addr_to_path,
	get_family,
	access_error,
	get_supported_socs,
)
import logging

logger = logging.getLogger("snagrecover")

default_usb_ids = {
	# default ROM code USB IDs
	"stm32mp": "0483:df11",
	"sama5": "03eb:6124",
	"sunxi": "1f3a:efe8",
	"am6x": {
		"am625": "0451:6165",
		"am62a7": "0451:6165",
		"am62d2": "0451:6165",
		"am62p": "0451:6165",
		"am6442": "0451:6165",
		"am654x": "0451:6165",
		"am623": "0451:6165",
		"am6411": "0451:6165",
		"am6412": "0451:6165",
		"am6421": "0451:6165",
		"am6422": "0451:6165",
		"am6441": "0451:6165",
		"am6548": "0451:6162",
		"am6546": "0451:6162",
	},
	"am62lx": "0451:6165",
	"zynqmp": "03fd:0050",
	"keembay": "8087:0b39",
	"imx": {
		"imx8qxp": "1fc9:012f",
		"imx8qm": "1fc9:0129",
		"imx8dxl": "1fc9:0147",
		"imx28": "15a2:004f",
		"imx815": "1fc9:013e",
		"imx865": "1fc9:0146",
		"imx91": "1fc9:0159",
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
		"imx53": "15a2:004e",
	},
	"bcm": {"bcm2711": "0a5c:2711", "bcm2712": "0a5c:2712"},
	"amlogic": "1b8e:c003",
}

recovery_config = {}  # Global immutable config to be initialized with CLI args


def check_soc_model(soc_model: str):
	socs = get_supported_socs()

	if soc_model not in {**socs["tested"], **socs["untested"]}:
		cli_error(
			f"unsupported soc model {soc_model}, supported socs: \n" + yaml.dump(socs)
		)
	return None


def complete_fw_paths(fw_config: dict, this_file_path: str) -> None:
	paths_relative_to_conf = fw_config.pop("paths-relative-to", "CWD")
	if paths_relative_to_conf == "CWD":
		return
	elif paths_relative_to_conf == "THIS_FILE":
		path_relative_to = os.path.dirname(this_file_path)
	else:
		path_relative_to = paths_relative_to_conf

	for binary in fw_config.keys():
		if "path" in fw_config[binary]:
			fw_config[binary]["path"] = os.path.join(
				path_relative_to, fw_config[binary]["path"]
			)


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
			usb_ids = default_usb_ids[soc_family]
			if isinstance(usb_ids, dict):
				usb_ids = usb_ids[soc_model]

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
				cli_error(
					"firmware config to CLI did not evaluate to Python3 dict: {fw}"
				)
			fw_configs = {**fw_configs, **fw}
		recovery_config["firmware"] = fw_configs
		if args.firmware_file:
			logger.warning(
				"You passed firmware configuration via files AND direct CLI arguments!"
			)
	if args.firmware_file:
		# get firmware configs
		for path in args.firmware_file:
			with open(path, "r") as file:
				fw_config_file = yaml.safe_load(file)
			if not isinstance(fw_config_file, dict):
				cli_error(
					f"firmware config passed to CLI did not evaluate to dict: {fw_config_file}"
				)
			complete_fw_paths(fw_config_file, path)
			fw_configs = {**fw_configs, **fw_config_file}
		recovery_config["firmware"] = fw_configs

	# store input arguments in config
	recovery_config["args"] = vars(args)
	logger.debug(f"recovery_config:{str(recovery_config)}")
