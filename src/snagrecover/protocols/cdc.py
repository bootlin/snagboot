import usb

INTF_CDC_DATA = 0xa

CDC_SET_LINE_CODING = 0x20
CDC_SET_CONTROL_LINE_STATE = 0x22

class CDCDevice():
	def __init__(self, dev, timeout: int):
		self.usb_dev = dev
		self.timeout = timeout
		self.usb_dev.default_timeout = timeout

		self.cfg = dev.configurations()[0]
		self.intf_data = self.cfg.interfaces()[1]

		if self.intf_data.bInterfaceClass != INTF_CDC_DATA:
			raise ValueError(f"Invalid interface class, expected CDC DATA ({INTF_CDC_DATA}), got {self.intf_data.bInterfaceClass}")

		endpoints = self.intf_data.endpoints()
		self.ep_in = None
		self.ep_out = None
		for ep in endpoints:
			direction = usb.util.endpoint_direction(ep.bEndpointAddress)
			if direction == usb.util.ENDPOINT_IN:
				self.ep_in = ep
			else:
				self.ep_out = ep

		if self.ep_in is None or self.ep_out is None:
			raise ValueError("Failed to find a pair of valid endpoints for this CDC device!")

		self.set_line_coding(115200)
		self.set_control_line_state(True, True)

	def set_line_coding(self, baudrate: int):
		# Hardcode parity and stop bits to 0, data bits to 8
		payload = int.to_bytes(baudrate, 4, "little") + b"\x00\x00\x08"
		self.usb_dev.ctrl_transfer(0x21, CDC_SET_LINE_CODING, 0, 0, payload)

	def set_control_line_state(self, carrier: bool, dte_present: bool):
		line_state = 0

		if carrier:
			line_state |= 0x2

		if dte_present:
			line_state |= 0x1

		self.usb_dev.ctrl_transfer(0x21, CDC_SET_CONTROL_LINE_STATE, line_state, 0, 0)

	def write(self, data: bytes):
		return self.ep_out.write(data)

	def read(self, num: int) -> bytes:
		chunk_size = self.ep_in.wMaxPacketSize
		data = b""

		nread = 0

		while nread < num:
			try:
				data += self.ep_in.read(chunk_size)
			except usb.core.USBTimeoutError:
				break

		return data

	def read_until(self, marker: bytes) -> bytes:
		chunk_size = self.ep_in.wMaxPacketSize
		data = b""

		while True:
			try:
				new_data = self.ep_in.read(chunk_size)

				if marker in new_data:
					index = new_data.index(marker)
					data += new_data[:index+1]
					break

				data += new_data[:]

			except usb.core.USBTimeoutError:
				break

		return data

	def close(self):
		self.set_control_line_state(False, False)
