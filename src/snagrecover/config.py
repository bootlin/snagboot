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
from snagrecover.utils import cli_error
import logging
logger = logging.getLogger("snagrecover")
import os

recovery_config = {} # Global immutable config to be initialized with CLI args

def get_family(soc_model: str) -> str:
        with open(os.path.dirname(__file__) + "/supported_socs.yaml", "r") as file:
                socs = yaml.safe_load(file)
        family = (socs["tested"] | socs["untested"])[soc_model]["family"]
        return family

def check_soc_model(soc_model: str):
	with open(os.path.dirname(__file__) + "/supported_socs.yaml", "r") as file:
		socs = yaml.safe_load(file)
	if soc_model not in socs["tested"] | socs["untested"]:
		cli_error(f"unsupported soc model {soc_model}, supported socs: \n" + yaml.dump(socs))
	return None

def init_config(args: list):
	#this is the only time that config.recovery_config should be modified!
	#get soc model
	soc_model = args.soc 
	check_soc_model(soc_model)
	recovery_config.update({"soc_model": soc_model})
	recovery_config.update({"soc_family": get_family(soc_model)})

	fw_configs = {}
	if args.firmware:
		for fw in args.firmware:
			if type(fw) != dict:
				cli_error("firmware config to CLI did not evaluate to Python3 dict: {fw}")
			fw_configs |= fw
		recovery_config["firmware"] = fw_configs
		if args.firmware_file:
			print("Warning: You passed firmware configuration via files AND direct CLI arguments.")
	if args.firmware_file:
		#get firmware configs
		for path in args.firmware_file:
			with open(path, "r") as file:
				fw_configs |= yaml.safe_load(file)
		if type(fw_configs) != dict:
			cli_error(f"firmware config passed to CLI did not evaluate to dict: {fw_configs}")
		recovery_config["firmware"] = fw_configs

	#store input arguments in config
	recovery_config["args"] = vars(args)
	logger.debug(f"recovery_config:{str(recovery_config)}")

