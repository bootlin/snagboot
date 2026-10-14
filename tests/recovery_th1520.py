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
		patcher = patch("snagrecover.firmware.firmware.Fastboot", return_value=self.fb)
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_download_flash_then_start(self) -> None:
		th1520_run(MagicMock(), "u-boot", FW_BLOB)

		self.fb.send.assert_called_once_with(FW_BLOB)
		# Commands must be sent without trailing NUL, as stock fastboot does
		self.assertEqual(
			[c.args[0] for c in self.fb.cmd.call_args_list],
			[b"flash:ram", b"reboot"],
		)

	def test_reboot_without_answer(self) -> None:
		def cmd(packet, *args, **kwargs):
			if packet == b"reboot":
				raise usb.core.USBError("device disconnected")

		self.fb.cmd.side_effect = cmd
		th1520_run(MagicMock(), "u-boot", FW_BLOB)
		self.assertEqual(self.fb.cmd.call_count, 2)

	def test_reboot_refused(self) -> None:
		def cmd(packet, *args, **kwargs):
			if packet == b"reboot":
				raise FastbootError("Fastboot fail with message: b'denied'")

		self.fb.cmd.side_effect = cmd
		with self.assertRaises(FastbootError):
			th1520_run(MagicMock(), "u-boot", FW_BLOB)

	def test_flash_failure_is_reported(self) -> None:
		def cmd(packet, *args, **kwargs):
			if packet == b"flash:ram":
				raise usb.core.USBError("transfer failed")

		self.fb.cmd.side_effect = cmd
		with self.assertRaises(usb.core.USBError):
			th1520_run(MagicMock(), "u-boot", FW_BLOB)
		self.assertEqual(self.fb.cmd.call_count, 1)

	def test_unsupported_firmware_name(self) -> None:
		with self.assertRaises(SystemExit):
			th1520_run(MagicMock(), "tiboot3", FW_BLOB)
		self.fb.send.assert_not_called()


if __name__ == "__main__":
	unittest.main()
