import logging
import tarfile
import struct

logger = logging.getLogger("snagrecover")

from dataclasses import dataclass
from snagrecover.utils import BinFileHeader
from fs import open_fs, errors
from pyfatfs import PyFATException
from io import BytesIO
from pathlib import Path
from os.path import normpath
from tempfile import TemporaryDirectory
from shutil import copy2
from time import sleep
from contextlib import nullcontext
from snagrecover.firmware.firmware import load_fw, get_fw_path
from snagrecover.protocols.bcm import (
	rom_code_send_file,
	BootcodeCommand,
	bootcode_get_command,
	bootcode_send_file_size,
	bootcode_send_file,
)
from snagrecover.config import recovery_config


def tar_getmember(tar: bytes | tarfile.TarFile, member_path: str) -> tarfile.TarInfo:
	"""
	return member (TarInfo) from tar archive.

	raise KeyError if member_path is not found in tar  archive.
	"""

	if isinstance(tar, tarfile.TarFile):
		bytes_context = nullcontext()
		tar_context = nullcontext(tar)
	else:
		bytes_context = BytesIO(tar)
		tar_context = tarfile.open(fileobj=bytes_context)

	with bytes_context, tar_context as tar_file:
		members_names = tar_file.getnames()

		# tar archive allows to update a file without recreating all the archive.
		# To do so, it append the new version to the archive, keeping the old version inside the archive.
		# We want to have the last version of a given file, look at lastly added file first (reverse).
		members_names.reverse()
		if len(members_names) == 0:
			err_msg = f"tar archive is empty, can't contain '{member_path}'"
			logger.warning(err_msg)
			raise KeyError(err_msg)

		for member_name in members_names:
			# Fix an "issue" where `tar_file.getmember("bootcode4.bin")` doesn't find "./bootcode4.bin" (and vice versa) inside the archive.
			# Depending on how you create the tar archive, file can be prepended with "./".
			if normpath(member_path) == normpath(member_name):
				if member_path != member_name:
					logger.debug(
						f"Tar member '{member_name}' match '{member_path}' using normalized path '{normpath(member_path)}'"
					)
				return tar_file.getmember(member_name)

		_norm_path = (
			f" ({normpath(member_path)})"
			if normpath(member_path) != member_path
			else ""
		)
		raise KeyError(f"{member_path}{_norm_path} is not present in the tar archive")


def tar_member_exist(tar: bytes | tarfile.TarFile, member_path: str) -> bool:
	"""
	Test if member_path is present in the given archive.
	"""
	file_exists = False
	try:
		tar_getmember(tar, member_path)
		file_exists = True
	except KeyError:
		pass

	return file_exists


def tar_extract_file(tar_blob: bytes, file_path: str) -> bytes:
	"""
	Extract file_path from tar_blob tar archive. file_path must point to a file/link inside tar_blob.
	raise ValueError if file_path is not a file/link (ie if extractfile returns None)
	"""
	with (
		BytesIO(tar_blob) as bootfiles_bin_file,
		tarfile.open(fileobj=bootfiles_bin_file) as tar_file,
	):
		member = tar_getmember(tar_file, file_path)
		member = tar_file.extractfile(member)
		if member is None:
			raise ValueError(
				f"{file_path} exists in tar archive but is is not a file or link"
			)
		file_bytes = member.read(-1)

	return file_bytes


def get_fileblob_from_bootfiles(
	tar_blob: bytes, file_name: str, file_paths: [str]
) -> bytes:
	"""
	tar_blob: bootfiles tar archive
	file_name: name of file, used for logging
	file_paths: paths to look for file_name inside the tar archive
	"""
	logger.debug(f"Searching for {file_paths} in 'bootfiles'")
	file_exist_paths = [x for x in file_paths if tar_member_exist(tar_blob, x)]
	logger.debug(f"Found {file_exist_paths} in 'bootfiles'")
	if len(file_exist_paths) == 0:
		err_msg = (
			f"'bootfiles' tar archive doesn't contain '{file_name}' ({file_paths})"
		)
		logger.critical(err_msg)
		raise FileNotFoundError(err_msg)

	file_path = file_exist_paths[0]
	if len(file_exist_paths) == 2:
		err_msg = f"Found two {file_name} in 'bootfiles' ({file_exist_paths})"
		logger.critical(err_msg)
		raise Exception(err_msg)

	logger.debug(f"Extracting '{file_name}' from 'bootfiles'...")
	try:
		return tar_extract_file(tar_blob, file_path)
	except ValueError as ve:
		err_msg = f"'bootfile'/{file_path} exists but is is not a file or link"
		logger.critical(err_msg)
		ve.add_note(err_msg)
		raise ve
	except tarfile.TarError as te:
		err_msg = f"Error when trying to extract 'bootfiles'/{file_path}"
		logger.critical(err_msg)
		te.add_note(err_msg)
		raise te


@dataclass
class MBR(BinFileHeader):
	bootstrap_code: bytes
	partition_entry_1: bytes
	partition_entry_2: bytes
	partition_entry_3: bytes
	partition_entry_4: bytes
	boot_signature: int

	fmt = "< 446s 16s 16s 16s 16s H"
	class_size = 512

	SECTOR_SIZE = 512
	BOOT_SIGNATURE = 0xAA55

	def is_valid(self) -> bool:
		return self.boot_signature == MBR.BOOT_SIGNATURE


@dataclass
class PartitionEntry(BinFileHeader):
	status: int
	chs_first_sector: bytes
	_type: int
	chs_last_sector: bytes
	lba_first_sector: int
	lba_nb_sectors: int

	fmt = "< B 3s B 3s I I"
	class_size = 16

	STATUS_ACTIVE_BIT = 7
	FAT_LBA_COMPATIBLE = [
		0x01,  # FAT12 (CHS/LBA)
		0x04,  # FAT16 (CHS/LBA)
		0x06,  # FAT12/16 (CHS/LBA)
		0x0B,  # FAT32 (CHS/LBA)
		0x0C,  # FAT32 (LBA)
		0x0E,  # FAT12/16 (LBA)
	]

	def is_active(self) -> bool:
		return self.status & (1 << PartitionEntry.STATUS_ACTIVE_BIT)

	def is_fat_lba(self) -> bool:
		return self.is_active() and self._type in PartitionEntry.FAT_LBA_COMPATIBLE

	def get_fat_start_offset(self) -> int:
		"""
		Get partition start offset in bytes.
		Partition type must be FAT with LBA.

		raise ValueError if is partition is not active or partition is not FAT with LBA.
		"""
		if self.is_fat_lba():
			return self.lba_first_sector * MBR.SECTOR_SIZE
		else:
			if self.is_active():
				raise ValueError(
					f"Partition type ({self._type:#04x}) is not FAT with LBA ([{','.join(f'{i:#04x}' for i in PartitionEntry.FAT_LBA_COMPATIBLE)}])"
				)
			else:
				raise ValueError(
					f"Partition is not active (partition status: {self.status:#04x})"
				)

	def __str__(self) -> str:
		return f"status: {self.status:#04x}, type: {self._type:#04x}, lba_first_sector: {self.lba_first_sector:#010x}({self.lba_first_sector}), lba_nb_sectors: {self.lba_first_sector:#010x}({self.lba_first_sector}) "


def should_modify_boot_fw() -> bool:
	return "u-boot" in recovery_config["firmware"]


def modify_boot_fw(boot_path: str, uboot_blob: bytes) -> None:
	"""
	Modify 'boot_path' disk image (MBR + FAT) to add U-Boot,
	remove Linux if present. Update config.txt settings' accordingly.
	"""
	logger.debug(f"Reading MBR from 'boot' firmware ({boot_path})")
	with open(boot_path, "rb") as bootimg:
		mbr_blob = bootimg.read(MBR.class_size)

	try:
		mbr = MBR.read(mbr_blob)
	except struct.error as se:
		logger.critical(f"Unexpected error while parsing MBR: {se}")
		raise se

	if not (mbr.is_valid()):
		err_msg = f"Invalid MBR in 'boot' firmware (MBR signature: {mbr.boot_signature} != {MBR.BOOT_SIGNATURE})"
		logger.critical(err_msg)
		raise Exception(err_msg)

	logger.debug(f"Parsing first partition entry ({mbr.partition_entry_1})")
	try:
		partition1 = PartitionEntry.read(mbr.partition_entry_1)
	except struct.error as se:
		logger.critical(f"Unexpected error while parsing first partition entry: {se}")
		raise se

	try:
		first_partition_offset = partition1.get_fat_start_offset()
		logger.debug(
			f"First partition FAT byte offset's: {first_partition_offset:#x} ({first_partition_offset})"
		)
	except ValueError as ve:
		logger.critical(ve)
		raise ve

	with open_fs(f"fat://{boot_path}?offset={first_partition_offset}") as bootimgfs:
		# IMPROVE fetch kernel path from config.txt
		# Workarround: existing files name are uppercased because they are not found otherwise (FAT SFN)
		kernel_path = "kernel8.img".upper()
		try:
			# removing kernel is optional but we might need the freed space
			# if more size is needed in future, can also delete initramfs (and remove it from settings)
			bootimgfs.remove(kernel_path)
			logger.debug(f"Removed '{kernel_path}' from 'boot' firmware ({boot_path})")
		except errors.ResourceNotFound:
			logger.debug(f"Can't delete '{kernel_path}'from 'boot' firmware: not found")

		uboot_path = "u-boot.bin"
		logger.debug(f"Writting '{uboot_path}' in 'boot' firmware ({boot_path})")
		try:
			bootimgfs.writebytes(uboot_path, uboot_blob)
		except PyFATException as pfe:
			err_msg = "Error when trying to add U-Boot to 'boot' firmware"
			logger.critical(err_msg)
			pfe.add_note(err_msg)
			raise pfe

		logger.debug(f"Updating 'config.txt' in 'boot' firmware ({boot_path})")
		config_path = "config.txt".upper()
		try:
			content = bootimgfs.readtext(config_path)
		except PyFATException as pfe:
			err_msg = f"Error while trying to read '{config_path}' from 'boot' firmware: {pfe}"
			logger.critical(err_msg)
			raise pfe

		# the last occurence of a settings is actually the one used
		content += "\n# Start of settings added by snagrecover\n"
		content += "[all]\n"
		content += "kernel=u-boot.bin\n"
		content += "arm_64bit=1\n"
		content += "# End of settings added by snagrecover\n"

		try:
			bootimgfs.writetext(config_path, content)
		except PyFATException as pfe:
			err_msg = (
				f"Error while trying to modify '{config_path}' from 'boot' firmware"
			)
			logger.critical(err_msg)
			pfe.add_note(err_msg)
			raise pfe

		logger.debug("Updated config.txt content's : " + content.replace("\n", "\\n"))
		logger.debug(f"'boot' firmware '/' directory content: {bootimgfs.listdir('/')}")


def bcm_run(port, fw_name: str, fw_blob: bytes, subfw_name: str) -> None:
	if fw_name != "bootfiles":
		# sanity check, right now we only have 'bootfiles' firmware
		err_msg = f"Unexpected firmware '{fw_name}'"
		logger.critical(err_msg)
		raise ValueError(err_msg)

	tar_blob = fw_blob
	soc_model = recovery_config["soc_model"]
	if soc_model == "bcm2711":
		subfolder_name = "2711"
		bootcode_name = "bootcode4.bin"
	elif soc_model == "bcm2712":
		subfolder_name = "2712"
		bootcode_name = "bootcode5.bin"
	else:
		# sanity check
		raise ValueError(f"Unexpected {soc_model=}")

	if subfw_name == "bootcode":
		bootcode_paths = [f"{subfolder_name}/{bootcode_name}", bootcode_name]
		bootcode_blob = get_fileblob_from_bootfiles(
			tar_blob, bootcode_name, bootcode_paths
		)

		logger.info(f"Sending 'bootfiles'/{bootcode_name} to ROM Code...")
		if transfer_res := rom_code_send_file(port, bootcode_blob):
			err_msg = f"Failed transfer of 'bootfiles' {bootcode_name} to ROM Code with status: {transfer_res}"
			logger.critical(err_msg)
			raise Exception(err_msg)

	elif subfw_name == "bootcode_firmwares":
		# Also handle firmwares 'boot' and 'u-boot'
		"""
		bootcode functions as a file client. It issues requests (GET_FILE_SIZE, GET_FILE) that we must serve.

		Procedure is as follows:
		1. get command and file name (bootcode_get_command)
		2. GET_FILE_SIZE command: send file size (bootcode_send_file_size)
		3. GET_FILE command: send file (bootcode_send_file)
		4. repeat above steps until DONE command
		"""

		if should_modify_boot_fw():
			boot_fw_path = get_fw_path("boot")
			tempdir = TemporaryDirectory()
			boot_fw_path_copy = copy2(boot_fw_path, f"{tempdir.name}/boot.img")
			logger.info(
				"U-Boot found in recovery config, copying 'boot' firmware and update it"
			)
			uboot_blob = load_fw("u-boot")
			modify_boot_fw(boot_fw_path_copy, uboot_blob)
		else:
			logger.debug(
				"U-Boot not found in recovery config, use unmodified 'boot' firmware"
			)

		logger.info("Serving bootcode requests...")
		command, file_name = bootcode_get_command(port)
		previous_file_name, previous_fw_blob = None, None
		while command != BootcodeCommand.DONE:
			logger.debug(
				f"Serving command '{command!r}' on requested file '{file_name}'"
			)

			if file_name == previous_file_name:
				# We expect GET_FILE_SIZE then GET_FILE on the same file, save us from reloading the blob
				requested_fw_blob = previous_fw_blob
			elif file_name in ["boot.img", "config.txt"]:
				firmware_name = Path(file_name).stem
				if firmware_name == "boot" and should_modify_boot_fw():
					file_path = boot_fw_path_copy
					requested_fw_blob = Path(file_path).read_bytes()
				else:
					file_path = get_fw_path(firmware_name)
					requested_fw_blob = load_fw(
						firmware_name, check_fw=(file_name != "config.txt")
					)
				logger.debug(
					f"'Requested file is '{file_name}', using firmware '{firmware_name}' ({file_path})"
				)
			else:
				file_paths = [f"{subfolder_name}/{file_name}", file_name]
				requested_fw_blob = get_fileblob_from_bootfiles(
					tar_blob, file_name, file_paths
				)

			if command == BootcodeCommand.GET_FILE_SIZE:
				bootcode_send_file_size(port, requested_fw_blob)
			elif command == BootcodeCommand.GET_FILE:
				bootcode_send_file(port, requested_fw_blob)
				logger.info(f"Served requested file for '{file_name}'")
				if file_name == "boot.img":
					logger.info("Waiting for 'boot' firmware to load...")
					sleep(3)

			previous_file_name, previous_fw_blob = file_name, requested_fw_blob
			(command, file_name) = bootcode_get_command(port)

		logger.info("Done serving bootcode requests")
		if should_modify_boot_fw():
			logger.debug(f"Cleanup temporary files ({boot_fw_path})")
			tempdir.cleanup()

	else:
		# sanity check
		err_msg = f"Unexpected firmware '{fw_name}'"
		logger.critical(err_msg)
		raise ValueError(err_msg)
