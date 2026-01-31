import unittest
import unittest.mock
import tempfile
import random

from snagflash.fastboot_uboot import SnagflashFastbootUboot, MMC_LBA_SIZE

MAX_IMAGE_LEN = 100000000
MAX_FLASH_OFFSET = 4096
MIN_FB_SIZE = 0x40000
MAX_FB_SIZE = 0xC000000

CHECK_SIZE = 0x1000


class TestFastbootUboot(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		fast = unittest.mock.Mock()
		cls.fb_uboot = SnagflashFastbootUboot(fast)
		cls.fb_uboot.env["fb-addr"] = "0x90000000"
		cls.fb_uboot.fb_size = random.randint(MIN_FB_SIZE, MAX_FB_SIZE)

		cls.image_file = tempfile.TemporaryFile("wb+")
		cls.image_len = random.randint(0, MAX_IMAGE_LEN)
		cls.image_file.write(random.randbytes(cls.image_len))

	@classmethod
	def tearDownClass(cls):
		cls.image_file.close()

	def test_flash_range(self):
		flash_func = unittest.mock.MagicMock()
		align = random.choice([MMC_LBA_SIZE, 0x40000])
		range_dst_offset = align * (random.randint(0, MAX_FLASH_OFFSET) // align)

		print(
			f"image len: {__class__.image_len}, dst_offset: {range_dst_offset}, align: {align}"
		)

		__class__.image_file.seek(0)

		__class__.fb_uboot.flash_range(
			__class__.image_file,
			flash_func,
			__class__.image_len,
			range_dst_offset,
			align,
		)

		with tempfile.TemporaryFile("wb+") as dst_file:
			for call in flash_func.mock_calls:
				_, blob, dst_offset = call.args

				# Write fits in Fastboot buffer
				self.assertTrue(len(blob) <= __class__.fb_uboot.fb_size)

				# Write is aligned
				self.assertEqual(dst_offset % align, 0)
				self.assertEqual(len(blob) % align, 0)

				dst_file.seek(dst_offset - range_dst_offset)
				dst_file.write(blob)

			dst_file.seek(0)
			__class__.image_file.seek(0)

			offset = 0
			while offset < __class__.image_len:
				if __class__.image_len - offset < CHECK_SIZE:
					rd_size = __class__.image_len - offset
				else:
					rd_size = CHECK_SIZE

				self.assertEqual(
					dst_file.read(rd_size),
					__class__.image_file.read(rd_size),
					msg=f"Incorrect write at offset 0x{offset:x}",
				)

				offset += rd_size
