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

from snagrecover.protocols import fastboot as fb
from snagrecover.utils import usb_addr_to_path, get_usb, access_error
import sys
import logging
logger = logging.getLogger("snagflash")

from snagflash.interactive import SnagflashInteractive

def fastboot(args):
	if (args.port is None):
		logger.info("Error: Missing command line argument --port vid:pid|bus-port1.port2.[...]")
		logger.error("Error: Missing command line argument --port vid:pid|bus-port1.port2.[...]")
		sys.exit(-1)

	usb_addr = usb_addr_to_path(args.port)
	if usb_addr is None:
		access_error("USB Fastboot", args.port)

	dev = get_usb(usb_addr)
	dev.default_timeout = int(args.timeout)

	fast = fb.Fastboot(dev, timeout = dev.default_timeout)

	# this is mostly there to dodge a linter error
	logger.debug(f"Fastboot object: eps {fast.ep_in} {fast.ep_out}")
	logger.info(args.fastboot_cmd)

	if hasattr(args, "factory"):
		session = SnagflashInteractive(fast)
		session.run(args.interactive_cmds)
		return

	for cmd in args.fastboot_cmd:
		cmd = cmd.split(":", 1)
		cmd, cmd_args = cmd[0], cmd[1:]
		cmd = cmd.replace("-", "_")
		logger.info(f"Sending command {cmd} with args {cmd_args}")
		if cmd == "continue":
			cmd = "fbcontinue"
		getattr(fast, cmd)(*cmd_args)

	logger.info("Done")

	session = None

	if args.interactive_cmdfile is not None:
		session = SnagflashInteractive(fast)
		logger.info(f"running commands from file {args.interactive_cmdfile}")
		with open(args.interactive_cmdfile, "r") as file:
			cmds = file.read(-1).splitlines()

		session.run(cmds)

	if args.interactive:
		if session is None:
			session = SnagflashInteractive(fast)

		session.start()

