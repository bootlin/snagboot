import unittest
from unittest.mock import MagicMock
from enum import Enum, auto

from snagrecover.protocols.fastboot import Fastboot, FastbootError

DUMMY_CMD: str = "test_cmd"
DUMMY_DATA: bytes = b"test_data"


class ResponseType(Enum):
	INFO = auto()
	TEXT = auto()
	FAIL = auto()
	OKAY = auto()
	DATA = auto()
	TIMEOUT = auto()


class TestFastboot(unittest.TestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.mock_device = MagicMock()

		# Mock endpoint with bulk IN/OUT attributes
		mock_ep_in = MagicMock()
		mock_ep_in.bmAttributes = 0x02  # ENDPOINT_TYPE_BULK
		mock_ep_in.bEndpointAddress = 0x81  # ENDPOINT_IN
		mock_ep_out = MagicMock()
		mock_ep_out.bmAttributes = 0x02  # ENDPOINT_TYPE_BULK
		mock_ep_out.bEndpointAddress = 0x01  # ENDPOINT_OUT

		# Mock interface with endpoints
		mock_intf = MagicMock()
		mock_intf.endpoints.return_value = [mock_ep_in, mock_ep_out]

		# Mock configuration with interfaces
		mock_cfg = MagicMock()
		mock_cfg.interfaces.return_value = [mock_intf]

		# Set up device mock
		cls.mock_device.get_active_configuration.return_value = mock_cfg

		cls.fastboot = Fastboot(cls.mock_device)

	def setUp(self) -> None:
		self.mock_device.reset_mock()

	def assert_device_write(self, expected_cmd: str) -> None:
		self.mock_device.write.assert_called_once_with(
			self.fastboot.ep_out, expected_cmd, timeout=self.fastboot.timeout
		)

	def expect_device_response(
		self, response_type: ResponseType, data: bytes = b""
	) -> None:
		read_value = response_type.name.encode() + data
		if response_type == ResponseType.TIMEOUT:
			self.mock_device.read.side_effect = TimeoutError()
			return

		self.mock_device.read.side_effect = [read_value]

	# --- Generic cmd tests ---

	def test_cmd_okay(self) -> None:
		self.expect_device_response(ResponseType.OKAY, DUMMY_DATA)
		result = self.fastboot.cmd(DUMMY_CMD)
		self.assert_device_write(DUMMY_CMD)
		self.assertEqual(result, DUMMY_DATA)

	def test_cmd_fail(self) -> None:
		self.expect_device_response(ResponseType.FAIL, DUMMY_DATA)
		with self.assertRaises(FastbootError):
			self.fastboot.cmd(DUMMY_CMD)
		self.assert_device_write(DUMMY_CMD)

	def test_cmd_info_or_text(self) -> None:
		for response in [ResponseType.INFO, ResponseType.TEXT]:
			with self.subTest(response=response):
				self.mock_device.reset_mock()
				self.mock_device.read.side_effect = [
					response.name.encode() + DUMMY_DATA,
					ResponseType.OKAY.name.encode() + b" waited for OKAY",
				]
				self.fastboot.cmd(DUMMY_CMD)
				self.assert_device_write(DUMMY_CMD)
