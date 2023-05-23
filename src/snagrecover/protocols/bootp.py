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

import logging
logger = logging.getLogger("snagrecover")

def parse_ipv4(addr: bytes) -> str:
	return f"{addr[0]}.{addr[1]}.{addr[2]}.{addr[3]}"

def parse_mac(addr: bytes) -> str:
	return f"{addr[0]:02x}:{addr[1]:02x}:{addr[2]:02x}:{addr[3]:02x}:{addr[4]:02x}:{addr[5]:02x}"

def encode_ipv4(addr: str) -> str:
	return bytes([int(x) for x in addr.split(".")])

def encode_filename(filename: str) -> bytes:
	return filename.encode('ascii') + b'\x00' * (128 - len(filename))

class BootpRequest():
	op_field = {
	1: "BOOT_REQUEST",
	2: "BOOT_REPLY"
	}

	DHCP_MSG_TYPE_TAG = 53
	DHCPACK = 5
	STOP_TAG = 255

	def __init__(self, packet: bytes):
		"""
		Parse BOOTP request packet (Format described in RFC 951)
		"""
		self.packet = packet
		self.op = BootpRequest.op_field[packet[0]]
		# packet[1]: htype, should be 1
		# packet[2]: hlen, should be 6
		# packet[3]: hops, should be 0
		self.xid = packet[4:8] # transaction id
		self.secs = int.from_bytes(packet[8:10], "big") # seconds since boot
		# packet[10:12]: unused
		self.ciaddr = parse_ipv4(packet[12:16]) # client ip, written by client
		self.yiaddr = parse_ipv4(packet[16:20]) #'your' (client) ip, written by server
		self.siaddr = parse_ipv4(packet[20:24]) # server ip
		# packet[24:28]: giaddr, gateway ip
		self.chaddr = parse_mac(packet[28:44]) # client mac address w/o padding
		# sname[44:108] optional server name
		self.file = packet[108:236] # boot file name
		# the rest of the packet contains vendor data and padding

	def build_reply(self, client_ip: str, server_ip:str, filename: str) -> bytes:
		reply = bytearray(self.packet)
		reply[0] = 2 # BOOTP_REPLY
		reply[16:20] = encode_ipv4(client_ip)
		reply[20:24] = encode_ipv4(server_ip)
		reply[108:236] = encode_filename(filename).lower()
		"""
		The vendor area of the packet can contain all sorts of
		additional data (see RFC1533 for a partial list). We are
		not trying to implement a fully functionnal BOOTP server so
		we do not parse and handle this area. However, SPL expects
		to find a DHCP ACK in the BOOTP packets it receives. Thus,
		we include this in every BOOTP response we send.
		"""
		# initialize vendor area to 0
		reply[240:300] = b"\x00" * 60
		# write DHCP ACK expected by SPL
		reply[240] = BootpRequest.DHCP_MSG_TYPE_TAG
		reply[241] = 1 # length of the field
		reply[242] = BootpRequest.DHCPACK # len
		# write stop tag
		reply[243] = BootpRequest.STOP_TAG
		return bytes(reply)

	def log(self):
		logger.debug("BootpRequest received packet:")
		logger.debug(f"transaction id: {self.xid}\n")
		logger.debug(f"seconds since boot attempt: {self.secs}\n")
		logger.debug(f"client ip: {self.ciaddr}\n")
		logger.debug(f"'your' (client) ip: {self.yiaddr}\n")
		logger.debug(f"server ip: {self.siaddr}\n")
		logger.debug(f"client hardware address: {self.chaddr}\n")
		logger.debug(f"boot file name: {self.file}\n")
		logger.debug("End of BootpRequest received packet")

