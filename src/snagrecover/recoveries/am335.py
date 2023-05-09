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

import serial
import time
from snagrecover.config import recovery_config
from snagrecover.firmware.firmware import install_firmware
import subprocess
import os

def main():
	if recovery_config["args"]["uart"]:
		port = serial.Serial(recovery_config["args"]["uart"], baudrate=recovery_config["args"]["baudrate"])
		install_firmware(port, "spl")
		install_firmware(port, "u-boot")
		port.close()
	else:
		#Check that we are running in the expected network namespace
		netns_name = recovery_config["args"]["netns"]
		bash_cmd = "ip netns identify " + str(os.getpid())
		process = subprocess.Popen(bash_cmd.split(), stdout=subprocess.PIPE)
		output, error = process.communicate()
		if output.decode("ascii") != f"{netns_name}\n":
			raise Exception(f"This recovery needs to be run in the {netns_name} namespace!\nDid you run sudo scripts/am335_usb_setup.sh?")

		#Install and run SPL
		install_firmware(None, "spl")
		#Install and run U-Boot
		install_firmware(None, "u-boot")

