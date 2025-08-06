import logging
import enum

logger = logging.getLogger("snagrecover")
from time import sleep
from snagrecover.utils import dnload_iter


def separate32b(blob_size32b: int) -> (int, int):
	"""
	return a tuple containing (16bits MSB, 16bits LSB) of a 32bits int
	"""
	assert blob_size32b > 0
	blob_size_16b_lsb = blob_size32b & 0xFFFF
	blob_size_16b_msb = (blob_size32b >> 16) & 0xFFFF

	return (blob_size_16b_msb, blob_size_16b_lsb)


def send_blob(dev, blob: bytes) -> None:
	"""
	Send blob to dev. If blob is empty, do nothing, no USB exchanges.

	Procedure is as follows:
	1. CONTROL OUT size of blob to send
	2. BULK send chunks of blob with chunck size of 16384 bytes.
	"""
	if len(blob) == 0:
		err_msg = "Trying to send a blob of len 0"
		logger.warning(err_msg)
		return ValueError(err_msg)

	blob_size = len(blob)
	logger.debug(f"Sending blob of size {blob_size} bytes to {dev=}...")
	(blob_size_16b_msb, blob_size_16b_lsb) = separate32b(blob_size)

	# First CONTROL OUT indicates the number of bytes that will be
	# transfered in the next BULKs transfers.
	dev.ctrl_transfer(
		bmRequestType=0x40,
		bRequest=0,
		wValue=blob_size_16b_lsb,
		wIndex=blob_size_16b_msb,
		data_or_wLength=0,
	)

	# we then send the blob in several bulk transfers
	for chunk in dnload_iter(blob, 16384):
		bulk_res = dev.write(1, chunk)
		if bulk_res != len(chunk):
			raise Exception(f"BULK OUT sent only {bulk_res}/{len(bulk_res)} bytes")


def rom_code_send_file(dev, file_blob: bytes) -> int:
	"""
	Send a file_blob to the ROM code.

	Procedure is as follows:
	1. send_blob(size of file_blob)
	2. send_blob(file_blob)
	3. CONTROL IN: get transfer result from ROM Code, 0 == SUCCES

	return transfer result from ROM Code, 0 == SUCCESS
	"""
	file_blob_size = len(file_blob)
	logger.debug(f"Sending {file_blob_size=} bytes to ROM Code")
	send_blob(dev, file_blob_size.to_bytes(24, "little", signed=False))

	send_blob(dev, file_blob)

	logger.debug("Waiting for ROM code to process file")
	sleep(2)
	ctrl_transfer_res = dev.ctrl_transfer(
		bmRequestType=0xC0, bRequest=0, wValue=0x0004, wIndex=0, data_or_wLength=4
	)
	rom_code_status = int.from_bytes(
		ctrl_transfer_res, byteorder="little", signed=False
	)
	logger.debug(f"ROM Code answered with {rom_code_status=}")

	return rom_code_status


class BootcodeCommand(enum.IntEnum):
	GET_FILE_SIZE = 0
	GET_FILE = 1
	DONE = 2

	def __repr__(self):
		return f"{self.name}:{self.value}"

	@classmethod
	def _missing_(cls, value):
		err_msg = f"Unsupported command '{value}'"
		logger.critical(err_msg)
		raise ValueError(err_msg)


def bootcode_get_command(dev) -> (BootcodeCommand, str):
	"""
	Get next command from bootcode.

	CONTROL IN: result on 260 bytes: 4bytes command int (little endian) and 256bytes file name

	return (command, filename)
	"""
	ctrl_transfer_res = dev.ctrl_transfer(
		bmRequestType=0xC0, bRequest=0, wValue=0x0104, wIndex=0, data_or_wLength=260
	)

	command = int.from_bytes(ctrl_transfer_res[0:4], byteorder="little", signed=False)
	command = BootcodeCommand(command)
	filename: str = ctrl_transfer_res[4:]
	try:
		filename = filename[0 : filename.index(0x00)]  # file name is null terminated
	except ValueError as ve:
		# index fails, filename is not null terminated
		err_msg = "file name received from bootcode is not null terminated"
		logger.critical(err_msg)
		logger.debug(f"{err_msg} {filename=}")
		ve.add_note(err_msg)
		raise ve

	filename = filename.tobytes().decode("ascii")

	return (command, filename)


def bootcode_send_file_size(dev, file_blob: bytes) -> None:
	"""
	Send file size to bootcode.

	Procedure is as follows:
	CONTROL OUT file_blob size
	"""
	file_blob_size = len(file_blob)
	(file_blob_size_16b_msb, file_blob_size_16b_lsb) = separate32b(file_blob_size)

	dev.ctrl_transfer(
		bmRequestType=0x40,
		bRequest=0,
		wValue=file_blob_size_16b_lsb,
		wIndex=file_blob_size_16b_msb,
		data_or_wLength=0,
	)


def bootcode_send_file(dev, file_blob: bytes) -> None:
	"""
	Send file to bootcode.

	Procedure is as follows:
	send_blob(file_blob)
	"""
	send_blob(dev, file_blob)
