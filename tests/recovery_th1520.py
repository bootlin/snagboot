import unittest
from unittest.mock import MagicMock, patch

import usb.core

from snagrecover.config import recovery_config
from snagrecover.firmware.firmware import th1520_run
from snagrecover.protocols.fastboot import FastbootError

FW_BLOB = b"\x01\x02\x03\x04" * 16


class TestTh1520Run(unittest.TestCase):
	def setUp(self) -> None:
		recovery_config.clear()
		self.fb = MagicMock()
		self.dev = MagicMock()
		patcher = patch("snagrecover.firmware.firmware.Fastboot", return_value=self.fb)
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_download_flash_then_start(self) -> None:
		th1520_run(self.dev, "u-boot", FW_BLOB)

		self.fb.send.assert_called_once_with(FW_BLOB)

		# Commands must be sent without trailing NUL, as stock fastboot does
		self.assertEqual(
			[c.args for c in self.fb.cmd.call_args_list],
			[(b"flash:ram",), ()],
		)
		self.fb.raw_cmd.assert_called_once_with(b"reboot")

	def test_reboot_without_answer(self) -> None:
		def cmd(packet=None, *args, **kwargs):
			if packet is None:
				raise usb.core.USBError("device disconnected")

		self.fb.cmd.side_effect = cmd
		th1520_run(self.dev, "u-boot", FW_BLOB)
		self.assertEqual(self.fb.cmd.call_count, 2)

	def test_reboot_write_failure_is_reported(self) -> None:
		self.fb.raw_cmd.side_effect = usb.core.USBError("transfer failed")
		with self.assertRaises(usb.core.USBError):
			th1520_run(self.dev, "u-boot", FW_BLOB)
		# The answer to reboot is not read when the write failed
		self.assertEqual(self.fb.cmd.call_count, 1)

	def test_reboot_refused(self) -> None:
		def cmd(packet=None, *args, **kwargs):
			if packet is None:
				raise FastbootError("Fastboot fail with message: b'denied'")

		self.fb.cmd.side_effect = cmd
		with self.assertRaises(FastbootError):
			th1520_run(self.dev, "u-boot", FW_BLOB)

	def test_flash_failure_is_reported(self) -> None:
		def cmd(packet=None, *args, **kwargs):
			if packet == b"flash:ram":
				raise usb.core.USBError("transfer failed")

		self.fb.cmd.side_effect = cmd
		with self.assertRaises(usb.core.USBError):
			th1520_run(self.dev, "u-boot", FW_BLOB)
		self.assertEqual(self.fb.cmd.call_count, 1)
		self.fb.raw_cmd.assert_not_called()


if __name__ == "__main__":
	unittest.main()
