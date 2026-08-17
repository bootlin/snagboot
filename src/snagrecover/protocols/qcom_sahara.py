# This file is part of Snagboot
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
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

"""
Qualcomm Sahara protocol implementation for EDL mode recovery.

Implements the Sahara protocol for transferring firmware images to
Qualcomm devices in Emergency Download (EDL) mode.
"""

import usb.core
import usb.util
import struct
import logging
import time
from dataclasses import dataclass

from snagrecover.utils import BinFileHeader as Header, dnload_iter

logger = logging.getLogger("snagrecover")


@dataclass
class SaharaHelloReq(Header):
	"""
	Sahara HELLO packet sent by the device (48 bytes, 12 little-endian uint32 fields).
	"""

	command: int
	length: int
	version: int
	version_min: int
	max_cmd_packet_length: int
	mode: int
	reserved1: int
	reserved2: int
	reserved3: int
	reserved4: int
	reserved5: int
	reserved6: int

	fmt = "<IIIIIIIIIIII"
	class_size = 48


@dataclass
class SaharaReadDataReq(Header):
	"""
	Sahara 32-bit READ_DATA packet sent by the device (20 bytes).
	"""

	command: int
	length: int
	image_id: int
	data_offset: int
	data_length: int

	fmt = "<IIIII"
	class_size = 20


@dataclass
class SaharaReadData64Req(Header):
	"""
	Sahara 64-bit READ_DATA packet sent by the device (32 bytes).
	"""

	command: int
	length: int
	image_id: int
	data_offset: int
	data_length: int

	fmt = "<IIQqq"
	class_size = 32


@dataclass
class SaharaEndImageTx(Header):
	"""
	Sahara END_IMAGE_TX packet sent by the device (16 bytes).
	"""

	command: int
	length: int
	image_id: int
	status: int

	fmt = "<IIII"
	class_size = 16


@dataclass
class SaharaDoneResp(Header):
	"""
	Sahara DONE_RESP packet sent by the device (12 bytes).
	"""

	command: int
	length: int
	status: int

	fmt = "<III"
	class_size = 12


class QSahara:
	"""
	QSahara protocol implementation for Qualcomm device recovery.

	This implementation follows the Qualcomm Sahara protocol specification
	for Emergency Download (EDL) mode device recovery. It uses an asynchronous,
	event-driven approach.
	"""

	# Sahara protocol command constants
	SAHARA_HELLO_REQ = 0x01
	SAHARA_HELLO_RESP = 0x02
	SAHARA_READ_DATA = 0x03        # 32-bit READ_DATA
	SAHARA_END_IMAGE_TX = 0x04
	SAHARA_DONE_REQ = 0x05
	SAHARA_DONE_RESP = 0x06
	SAHARA_RESET_REQ = 0x07
	SAHARA_READ_DATA_64 = 0x12     # 64-bit READ_DATA

	# USB packet size - must match MHI_MAX_MTU
	SAHARA_PACKET_MAX_SIZE = 0xFFFF  # 65535 bytes

	# Maps each Sahara command to the name of the method that handles it
	COMMAND_HANDLERS = {
		SAHARA_HELLO_REQ: "handle_hello",
		SAHARA_READ_DATA: "handle_read_data",
		SAHARA_READ_DATA_64: "handle_read_data_64",
		SAHARA_END_IMAGE_TX: "handle_end_image_tx",
		SAHARA_DONE_RESP: "handle_done_resp",
	}

	def __init__(self, usb_dev):
		"""
		Initialize QSahara protocol handler.

		Args:
			usb_dev: PyUSB device object for the Qualcomm device in EDL mode
		"""
		self.dev = usb_dev
		self.ep_in = None
		self.ep_out = None

		# State management for event-driven processing
		self.running = False
		self.error = None
		self.current_image_id = None
		self.current_image_data = None

		# Track active image ID for validation
		# The device sends READ_DATA with an image ID, and all subsequent
		# READ_DATA requests must use the same ID until END_IMAGE_TX
		self.active_image_id = None

		# Find USB bulk endpoints
		self.find_endpoints()

		# Get and cache the USB max packet size
		self.max_packet_size = self.get_max_packet_size()

		logger.info("QSahara protocol initialized")

	def find_endpoints(self):
		"""
		Discover USB bulk IN and OUT endpoints.

		The Qualcomm device in EDL mode uses bulk endpoints for
		Sahara protocol communication.

		Raises:
			RuntimeError: If bulk endpoints cannot be found
		"""
		cfg = self.dev.get_active_configuration()
		intf = cfg[(0, 0)]

		# Find bulk IN endpoint
		ep_in = usb.util.find_descriptor(
			intf,
			custom_match=lambda e: (
				usb.util.endpoint_type(e.bmAttributes) ==
				usb.util.ENDPOINT_TYPE_BULK and
				usb.util.endpoint_direction(e.bEndpointAddress) ==
				usb.util.ENDPOINT_IN
			)
		)

		# Find bulk OUT endpoint
		ep_out = usb.util.find_descriptor(
			intf,
			custom_match=lambda e: (
				usb.util.endpoint_type(e.bmAttributes) ==
				usb.util.ENDPOINT_TYPE_BULK and
				usb.util.endpoint_direction(e.bEndpointAddress) ==
				usb.util.ENDPOINT_OUT
			)
		)

		if ep_in is None or ep_out is None:
			raise RuntimeError("Could not find bulk endpoints")

		self.ep_in = ep_in.bEndpointAddress
		self.ep_out = ep_out.bEndpointAddress

		logger.debug(f"Found endpoints: IN={self.ep_in:#x}, OUT={self.ep_out:#x}")

	def get_max_packet_size(self):
		"""
		Get the maximum packet size from USB endpoint descriptor.

		This reads the wMaxPacketSize field from the OUT endpoint descriptor,
		which indicates the maximum number of bytes that can be sent in a single
		USB packet. This is typically:
		- 512 bytes for USB 2.0 bulk endpoints
		- 1024 bytes for USB 3.0 bulk endpoints

		Returns:
			int: Maximum packet size in bytes
		"""
		try:
			# Get the active configuration
			cfg = self.dev.get_active_configuration()

			# Find the OUT endpoint descriptor
			ep_desc = usb.util.find_descriptor(
				cfg[(0, 0)],
				custom_match=lambda e: e.bEndpointAddress == self.ep_out
			)

			if ep_desc and hasattr(ep_desc, 'wMaxPacketSize'):
				max_packet_size = ep_desc.wMaxPacketSize
				logger.debug(f"USB max packet size from descriptor: {max_packet_size} bytes")
				return max_packet_size
		except Exception as e:
			logger.warning(f"Could not read max packet size from descriptor: {e}")

		# Fallback to 512 bytes (USB 2.0 bulk endpoint standard)
		logger.debug("Using fallback max packet size: 512 bytes (USB 2.0 standard)")
		return 512

	def send_chunk(self, data):
		"""
		Send a single data chunk via USB bulk endpoint.

		Args:
			data: bytes to send (typically ≤64KB)

		Returns:
			int: Number of bytes written

		Raises:
			IOError: If write fails or incomplete
		"""
		bytes_written = self.dev.write(self.ep_out, data)

		if bytes_written != len(data):
			raise IOError(
				f"USB write incomplete: expected {len(data)} bytes, "
				f"wrote {bytes_written} bytes"
			)

		return bytes_written

	def send_zlp_if_needed(self, total_bytes_sent):
		"""
		Send Zero-Length Packet if total transfer size is aligned to max packet size.

		ZLP is required by the USB protocol when the total transfer size is an
		exact multiple of the maximum packet size. Without ZLP, the device cannot
		distinguish between "transfer complete" and "more data coming", causing
		it to wait indefinitely.

		This must be called ONCE after ALL chunks of a transfer are sent, not
		after each individual chunk.

		Args:
			total_bytes_sent: Total number of bytes sent in the complete transfer
		"""
		if total_bytes_sent % self.max_packet_size == 0:
			logger.debug(
				f"Total transfer size {total_bytes_sent} is multiple of "
				f"max packet size {self.max_packet_size}, sending ZLP"
			)
			zlp_written = self.dev.write(self.ep_out, b'')
			logger.debug(f"ZLP sent ({zlp_written} bytes)")

	def transfer_image(self, image_id, data):
		"""
		Transfer firmware image to device.
		Main entry point that starts the event-driven processing loop.

		Args:
			image_id: Sahara image ID
			data: Firmware binary data (bytes)

		Raises:
			Exception: Any error that occurred during transfer
		"""
		logger.debug(f"Starting transfer of image ID {image_id:#x}, size {len(data)} bytes")

		# Setup state for this transfer
		self.current_image_id = image_id
		self.current_image_data = data
		self.running = True
		self.error = None

		# Start the event-driven processing loop
		# Note: For subsequent images, the device will send HELLO first
		self.processing_loop()

		# Check for errors after loop completes
		if self.error:
			raise self.error

		logger.debug(f"Successfully transferred image ID {image_id:#x}")

	def processing_loop(self):
		"""
		Main event loop - waits for packets and dispatches them.

		The loop continues until:
		- Transfer completes successfully (DONE_RESP received)
		- Protocol error occurs
		"""
		while self.running:
			try:
				# Wait for next packet
				logger.debug("Waiting for next packet from device...")
				packet = self.receive_packet()

				# Dispatch to appropriate handler based on command
				self.dispatch_packet(packet)

			except Exception as e:
				logger.error(f"Protocol error: {e}")
				# Send RESET to leave device in clean state for retry
				self.send_reset()
				self.error = e
				self.running = False

	def receive_packet(self):
		"""
		Receive a packet from the device. Times out after 10 seconds.

		USB bulk transfers send complete packets atomically. We must provide
		a buffer large enough for the maximum possible packet size, otherwise
		we get an overflow error if the device sends more data than our buffer.

		Returns:
			bytes: Complete packet data

		Raises:
			usb.core.USBError: On USB communication error or timeout
			ValueError: If packet is malformed
		"""
		try:
			# 10 second timeout
			data = bytes(self.dev.read(
				self.ep_in, self.SAHARA_PACKET_MAX_SIZE, timeout=10000
			))
		except Exception as e:
			logger.error(f"Timeout or error waiting for packet from device: {e}")
			raise

		if len(data) < 8:
			raise ValueError(f"Received undersized packet: {len(data)} bytes")

		# Parse header to get actual packet length
		command, length = struct.unpack('<II', data[:8])

		logger.debug(f"RECEIVED: cmd={command:#x} length={length} actual_bytes={len(data)}")

		# Validate that we received the complete packet
		if len(data) < length:
			raise ValueError(
				f"Incomplete packet: expected {length} bytes, got {len(data)} bytes"
			)

		# Return only the actual packet (trim any extra bytes)
		packet = data[:length]

		logger.debug(f"  First 24 bytes: {packet[:24].hex(' ')}")
		if len(packet) > 24:
			logger.debug(f"  Last 24 bytes: {packet[-24:].hex(' ')}")

		return packet

	def dispatch_packet(self, packet):
		"""
		Dispatch packet to appropriate handler based on command.
		Similar to Linux kernel switch statement in sahara_processing().

		Args:
			packet: Raw packet data

		Raises:
			ValueError: If command is unknown
		"""
		command = struct.unpack('<I', packet[:4])[0]

		logger.debug(f"Dispatching command {command:#x}")

		handler_name = self.COMMAND_HANDLERS.get(command)
		if handler_name is None:
			raise ValueError(f"Unknown command: {command:#x}")

		getattr(self, handler_name)(packet)

	def handle_hello(self, packet):
		"""
		Handle HELLO packet from device.

		Args:
			packet: HELLO packet data (48 bytes)
		"""
		hello = SaharaHelloReq.read(packet)

		logger.info(
			f"Received HELLO message from device. "
			f"Protocol version: {hello.version:#x}, Mode: {hello.mode:#x}"
		)

		# Validate packet length
		if hello.length != 48:
			raise ValueError(f"Invalid HELLO length: {hello.length}")

		# Send HELLO_RESP
		logger.info("Sending HELLO RESPONSE message to device")
		self.send_hello_response(hello.version, hello.mode)

	def handle_read_data(self, packet):
		"""
		Handle READ_DATA request from device.

		Args:
			packet: READ_DATA packet data (20 bytes)
		"""
		req = SaharaReadDataReq.read(packet)
		image_id = req.image_id
		offset = req.data_offset
		length = req.data_length

		# Validate image ID. First READ_DATA sets the active image ID
		# All subsequent READ_DATA must use the same ID until END_IMAGE_TX
		if self.active_image_id is None:
			# First READ_DATA for this image - set active image ID
			self.active_image_id = image_id
			logger.info(f"Received first READ DATA (32-bit) message from device")
			logger.debug(f"Device requesting image ID {image_id:#x}")

			# Validate it matches what we're trying to send
			if image_id != self.current_image_id:
				raise ValueError(
					f"Image ID mismatch: device requested {image_id:#x}, "
					f"but we're trying to send {self.current_image_id:#x}"
				)
		else:
			# Subsequent READ_DATA - must match active image ID
			if image_id != self.active_image_id:
				raise ValueError(
					f"Image ID mismatch: active image is {self.active_image_id:#x}, "
					f"but device requested {image_id:#x}"
				)

		logger.debug(f"Device requests data: offset={offset} length={length} bytes")

		# Validate offset and length
		if offset >= len(self.current_image_data):
			raise ValueError(f"Invalid offset {offset}, image size {len(self.current_image_data)}")

		if offset + length > len(self.current_image_data):
			raise ValueError(
				f"Invalid read: offset={offset} length={length}, "
				f"image size={len(self.current_image_data)}"
			)

		# Extract requested data
		data = self.current_image_data[offset:offset+length]

		# Send data in chunks to avoid USB buffer limitations in the USB stack
		# Chunking ensures all data is actually transmitted
		total_bytes_sent = 0
		chunk_count = 0

		logger.debug(f"Sending {len(data)} bytes to device")
		if len(data) > 0:
			logger.debug(f"  First 24 bytes: {data[:24].hex(' ')}")
			if len(data) > 24:
				logger.debug(f"  Last 24 bytes: {data[-24:].hex(' ')}")

		for chunk_data in dnload_iter(data, self.SAHARA_PACKET_MAX_SIZE + 1):
			chunk_count += 1
			# Send chunk using helper function (no ZLP yet)
			bytes_written = self.send_chunk(chunk_data)
			total_bytes_sent += bytes_written

		logger.debug(f"Successfully sent {total_bytes_sent} bytes in {chunk_count} chunks")

		# Send Zero-Length Packet (ZLP) if needed - ONCE after ALL chunks
		# ZLP is required when TOTAL data size is a multiple of USB max packet size
		# to signal end of transfer.
		self.send_zlp_if_needed(total_bytes_sent)

	def handle_read_data_64(self, packet):
		"""
		Handle 64-bit READ_DATA request from device.

		This is similar to handle_read_data but uses 64-bit fields for
		image_id, offset, and length to support larger images.

		Args:
			packet: READ_DATA_64 packet data (32 bytes)
		"""
		req = SaharaReadData64Req.read(packet)
		image_id = req.image_id
		offset = req.data_offset
		length = req.data_length

		# Validate image ID. First READ_DATA sets the active image ID
		# All subsequent READ_DATA must use the same ID until END_IMAGE_TX
		if self.active_image_id is None:
			# First READ_DATA for this image - set active image ID
			self.active_image_id = image_id
			logger.info(f"Received first READ DATA (64-bit) message from device")
			logger.debug(f"Device requesting image ID {image_id:#x}")

			# Validate it matches what we're trying to send
			if image_id != self.current_image_id:
				raise ValueError(
					f"Image ID mismatch: device requested {image_id:#x}, "
					f"but we're trying to send {self.current_image_id:#x}"
				)
		else:
			# Subsequent READ_DATA - must match active image ID
			if image_id != self.active_image_id:
				raise ValueError(
					f"Image ID mismatch: active image is {self.active_image_id:#x}, "
					f"but device requested {image_id:#x}"
				)

		logger.debug(f"Device requests data (64-bit): offset={offset} length={length} bytes")

		# Validate offset and length (with 64-bit support)
		if offset >= len(self.current_image_data):
			raise ValueError(f"Invalid offset {offset}, image size {len(self.current_image_data)}")

		if offset + length > len(self.current_image_data):
			raise ValueError(
				f"Invalid read: offset={offset} length={length}, "
				f"image size={len(self.current_image_data)}"
			)

		# Extract requested data
		data = self.current_image_data[offset:offset+length]

		# Send data in chunks to avoid Linux USB buffer limitations
		# Linux USB subsystem may truncate large transfers (e.g., 1MB → 240KB)
		# Chunking ensures all data is actually transmitted
		total_bytes_sent = 0
		chunk_count = 0

		logger.debug(f"Sending {len(data)} bytes to device")
		if len(data) > 0:
			logger.debug(f"  First 24 bytes: {data[:24].hex(' ')}")
			if len(data) > 24:
				logger.debug(f"  Last 24 bytes: {data[-24:].hex(' ')}")

		for chunk_data in dnload_iter(data, self.SAHARA_PACKET_MAX_SIZE + 1):
			chunk_count += 1
			# Send chunk using helper function (no ZLP yet)
			bytes_written = self.send_chunk(chunk_data)
			total_bytes_sent += bytes_written

		logger.debug(f"Successfully sent {total_bytes_sent} bytes in {chunk_count} chunks")

		# Send Zero-Length Packet (ZLP) if needed - ONCE after ALL chunks
		# ZLP is required when TOTAL data size is a multiple of USB max packet size
		# to signal end of transfer.
		self.send_zlp_if_needed(total_bytes_sent)

	def handle_end_image_tx(self, packet):
		"""
		Handle END_IMAGE_TX from device.

		Args:
			packet: END_IMAGE_TX packet data (16 bytes)
		"""
		end_tx = SaharaEndImageTx.read(packet)
		image_id = end_tx.image_id
		status = end_tx.status

		logger.info(f"Received END IMAGE TX message from device. Status: {status}")
		logger.debug(f"Device finished receiving image. Image ID: {image_id:#x}")

		# Validate image ID matches active image
		if self.active_image_id is not None and image_id != self.active_image_id:
			raise ValueError(
				f"END_IMAGE_TX image ID {image_id:#x} does not match "
				f"active image {self.active_image_id:#x}"
			)

		# Release the active image This allows the next image transfer
		# to set a new active_image_id
		logger.debug(f"Releasing image ID {self.active_image_id:#x}")
		self.active_image_id = None

		if status != 0:
			raise RuntimeError(f"Image transfer failed with status {status}")

		# Device will now process the image
		logger.info("Sending DONE message to device")
		self.send_done()
		logger.debug("Waiting for DONE RESPONSE message from device")

	def handle_done_resp(self, packet):
		"""
		Handle DONE_RESP from device - transfer complete!

		Args:
			packet: DONE_RESP packet data (12 bytes)
		"""
		done_resp = SaharaDoneResp.read(packet)
		status = done_resp.status

		logger.info(f"Received DONE RESPONSE message from device. Status: {status}")

		# Note: Intentional do nothing as we don't need to exit an app,
		# until all the images are transferred.
		self.running = False

	def send_hello_response(self, version, mode):
		"""
		Send HELLO_RESP packet to device.

		Args:
			version: Protocol version from device
			mode: Mode from device
		"""
		packet = struct.pack(
			'<IIIIIIIIIIII',  # 12 uint32_t fields (little-endian)
			self.SAHARA_HELLO_RESP,  # command
			48,                       # length
			version,                  # version
			version,                  # version_min (same as version)
			0,                        # status (0 = success)
			mode,                     # mode (echo back)
			0, 0, 0, 0, 0, 0         # reserved fields
		)
		logger.debug(f"Sending HELLO_RESP packet ({len(packet)} bytes)")
		logger.debug(f"  First 24 bytes: {packet[:24].hex(' ')}")
		logger.debug(f"  Last 24 bytes: {packet[-24:].hex(' ')}")
		self.dev.write(self.ep_out, packet)

	def send_done(self):
		"""
		Send DONE command to device.
		"""
		packet = struct.pack(
			'<II',  # 2 uint32_t fields (little-endian)
			self.SAHARA_DONE_REQ,  # command
			8                       # length
		)
		logger.debug(f"Sending DONE packet ({len(packet)} bytes)")
		logger.debug(f"  First 24 bytes: {packet[:24].hex(' ')}")
		self.dev.write(self.ep_out, packet)

	def send_reset(self):
		"""
		Send RESET command to device.

		This resets the device's Sahara protocol state, allowing it to restart
		the transfer process.

		Called before raising exceptions to leave the device in a clean state
		for potential retry attempts.
		"""
		try:
			logger.info("Sending RESET message to device...")
			packet = struct.pack(
				'<II',  # 2 uint32_t fields (little-endian)
				self.SAHARA_RESET_REQ,  # command
				8                        # length
			)
			logger.debug(f"Sending RESET packet ({len(packet)} bytes)")
			logger.debug(f"  First 24 bytes: {packet[:24].hex(' ')}")
			self.dev.write(self.ep_out, packet)
			logger.info("RESET message sent - device should be in clean state")
		except Exception as e:
			# Don't fail if reset fails - we're already in error handling
			logger.warning(f"Failed to send RESET message: {e}")

	def close(self):
		"""
		Clean up resources.
		"""
		self.running = False
		logger.info("QSahara protocol closed")
