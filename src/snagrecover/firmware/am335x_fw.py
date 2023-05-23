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

from snagrecover.config import recovery_config
from snagrecover.protocols import bootp
import socketserver
import socket
import time
import logging
logger = logging.getLogger("snagrecover")
from xmodem import XMODEM
# setting this logger to the same format as the main
# logger since it sometimes prints out messages that seem
# like fatal errors but are apparently benign
xmodem_logger = logging.getLogger("xmodem.XMODEM")
xmodem_logger.parent = logger
import tftpy
import threading
import os.path

server_config = {
	"listen": "0.0.0.0",
	# The values chosen for the client and server ips
	# basically do not matter, as we run the recovery
	# inside an isolated network namespace.
	# However, they must match with the values
	# used in the am335x helper scripts
	"server_ip": "192.168.0.100",
	"client_ip": "192.168.0.101",
	"bootp_port": 9067,
	"bootp_timeout": 10,
	"tftp_port": 9069,
	"tftp_start_timeout": 30,
	"tftp_complete_timeout": 180,
}

def tftp_proc(server: tftpy.TftpServer):
	logger.info("Starting TFTP server...")
	tftp_port = server_config["tftp_port"]
	server.listen(server_config["listen"], tftp_port, timeout=1)
	logger.info("TFTP server finished")

def bootp_proc(server: socketserver.UDPServer):
	logger.info("Starting BOOTP server...")
	server.serve_forever()
	logger.info("BOOTP server finished")

class UDPHandler(socketserver.BaseRequestHandler):

	def handle(self):
		data = self.request[0].strip()
		sock = self.request[1]
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
		logger.debug(f"packet from {self.client_address[0]}")
		bootp_req = bootp.BootpRequest(data)
		bootp_req.log()
		fw_name = self.server.fw_name
		# address that the client will use as its IP source in further communications
		assigned_client_ip = server_config["client_ip"]
		# address that the board can use to contact the bootp and tftp servers
		server_ip = server_config["server_ip"]
		filename = os.path.basename(recovery_config["firmware"][fw_name]["path"])
		reply = bootp_req.build_reply(assigned_client_ip, server_ip, filename)
		sock.sendto(reply, ("<broadcast>", self.client_address[1]))

def am335x_usb(port, fw_name: str):
	tftp_start_timeout = server_config["tftp_start_timeout"]
	tftp_complete_timeout = server_config["tftp_complete_timeout"]
	# TFTP server thread
	tftp_server = tftpy.TftpServer(os.path.dirname(recovery_config["firmware"][fw_name]["path"]))
	tftp_thread = threading.Thread(name="Recovery TFTP server for AM335x", target=tftp_proc, args=[tftp_server])
	tftp_thread.daemon = True

	# BOOTP server thread
	listen_address = server_config["listen"]
	bootp_port = server_config["bootp_port"]
	bootp_server = socketserver.UDPServer((listen_address, bootp_port), UDPHandler)
	bootp_server.timeout = server_config["bootp_timeout"]
	bootp_server.fw_name = fw_name
	bootp_thread = threading.Thread(name="Recovery BOOTP server for AM335x", target=bootp_proc, args=[bootp_server])
	bootp_thread.daemon = True

	print("Starting TFTP server...")
	tftp_thread.start()
	print("Starting BOOTP server...")
	bootp_thread.start()

	t0 = time.time()
	while tftp_server.sessions == {}:
		if time.time() - t0 > tftp_start_timeout:
			raise Exception("Timeout waiting for TFTP request")
		time.sleep(0.1)
	t0 = time.time()
	while tftp_server.sessions != {}:
		if time.time() - t0 > tftp_complete_timeout:
			raise Exception("Timeout waiting for TFTP transfer to complete")
		time.sleep(0.1)

	# Note that this will not interrupt a tftp transfer in progress
	tftp_server.stop()
	logger.info("Waiting for TFTP server to stop...")
	print("Waiting for TFTP shutdown...")
	tftp_thread.join()
	bootp_server.shutdown()
	bootp_server.server_close()
	print("Waiting for BOOTP shutdown...")
	logger.info("Waiting for BOOTP server to stop...")
	bootp_thread.join()

def am335x_uart(port, fw_name: str):
	TRANSFER_WAIT_TIMEOUT = 5
	if fw_name == "u-boot":
		print("Transfering U-Boot over a UART connection, this could take a while...")

	def getc(size, timeout=1):
		port.write_timeout = timeout
		return port.read(size) or None

	def putc(data, timeout=1):
		port.timeout = timeout
		return port.write(data)

	modem = XMODEM(getc, putc)
	logger.info("Waiting for ping before xmodem transfer...")
	t0 = time.time()
	while port.read(1) != b"C":
		if time.time() - t0 > TRANSFER_WAIT_TIMEOUT:
			raise Exception("Timeout waiting for UART ping")
	fw_path = recovery_config["firmware"][fw_name]["path"]
	with open(fw_path, "rb") as file:
		logger.info(f"Transfering {fw_path} using xmodem...")
		modem.send(file)
	logger.info("xmodem transfer done")

def am335x_run(port, fw_name: str):
	if recovery_config["args"]["uart"]:
		am335x_uart(port, fw_name)
	else:
		am335x_usb(port, fw_name)

