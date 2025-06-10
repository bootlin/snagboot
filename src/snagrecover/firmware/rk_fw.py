#!/usr/bin/python3
# Copyright 2025 Collabora Ltd.
#
# SPDX-License-Identifier: GPL-2.0+
#
# Author: Arnaud Patard <arnaud.patard@collabora.com>
#
# Notes:
# to unpack / descramble encrypted parts, the rc4 key is inside u-boot's code.
# Some information used here are coming from rkdeveloptool, which is GPL-2.0+

import logging
import struct
import time
from crccheck import crc
from dataclasses import dataclass

logger = logging.getLogger("snagrecover")
from snagrecover.protocols import rockchip
from snagrecover.protocols import dfu
from snagrecover.utils import BinFileHeader
from snagrecover.config import recovery_config


# List generated with a grep on rkbin repository
NEWIDB_LIST = ["rk3506", "rk3506b", "rk3528", "rk3562", "rk3566", "rk3568", "rk3576", "rk3583", "rk3588", "rv1103b", "rv1106"]

BOOTTAG = b"BOOT"
LDRTAG = b"LDR "
TAG_LIST = [BOOTTAG, LDRTAG]
BOOTENTRYSIZE = 57
BOOTHEADERENTRYSIZE = 6
BOOTHEADERSIZE = 102
BOOTHEADERTIMESIZE = 7
RC4_KEY = bytearray([124, 78, 3, 4, 85, 5, 9, 7, 45, 44, 123, 56, 23, 13, 23, 17])


@dataclass
class BootEntry(BinFileHeader):
	size: int
	type: int
	name: bytes
	data_offset: int
	data_size: int
	data_delay: int

	fmt = "<BI40sIII"
	class_size = BOOTENTRYSIZE

	def __str__(self):
		name = self.name.decode('utf-16le')
		return f"Entry {name} (type: {self.type}, size: {self.size}, data offset: {self.data_offset}, data size: {self.data_size}, delay: {self.data_delay})"


@dataclass
class BootHeaderEntry(BinFileHeader):
	count: int
	offset: int
	size: int

	fmt = "<BIB"
	class_size = BOOTHEADERENTRYSIZE


@dataclass
class BootReleaseTime(BinFileHeader):
	year: int
	month: int
	day: int
	hour: int
	minute: int
	second: int

	fmt = "<HBBBBB"
	class_size = BOOTHEADERTIMESIZE

	def __str__(self):
		return f"{self.year}/{self.month}/{self.day} {self.hour}:{self.minute}:{self.second}"


class LoaderFileError(Exception):
	def __init__(self, message):
		self.message = message
		super().__init__(self.message)

	def __str__(self):
		return f"File format error: {self.message}"


@dataclass
class BootHeader(BinFileHeader):
	tag: bytes
	size: int
	version: int
	merge_version: int
	releasetime: BootReleaseTime
	chip: bytes
	entry471: BootHeaderEntry
	entry472: BootHeaderEntry
	loader: BootHeaderEntry
	sign: int
	# 1 : disable rc4
	rc4: int
	reserved: bytes

	fmt = f"<4sHII{BOOTHEADERTIMESIZE}s4s{BOOTHEADERENTRYSIZE}s{BOOTHEADERENTRYSIZE}s{BOOTHEADERENTRYSIZE}sBB57s"
	class_size = BOOTHEADERSIZE

	def __post_init__(self):
		if self.tag not in TAG_LIST:
			raise LoaderFileError(f"Invalid tag {self.tag}")
		# not sure how to exactly parse version/merge_version
		self.maj_ver = self.version >> 8
		self.min_ver = self.version & 0xff
		self.releasetime = BootReleaseTime.read(self.releasetime, 0)
		# the code should possible check that the soc_model in cfg is matching
		# this information but a mapping is needed.
		self.chip = self.chip[::-1]
		self.entry471 = BootHeaderEntry.read(self.entry471, 0)
		self.entry472 = BootHeaderEntry.read(self.entry472, 0)
		self.loader = BootHeaderEntry.read(self.loader, 0)
		if self.rc4:
			self.rc4 = False
		else:
			self.rc4 = True
		if self.sign == 'S':
			self.sign = True
		else:
			self.sign = False

	def __str__(self):
		return f"{self.tag}, {self.size} ,{self.maj_ver}.{self.min_ver}, 0x{self.merge_version:0x}, {self.releasetime}, {self.chip}, {self.entry471}, {self.entry472}, {self.loader}, sign: {self.sign}, enc: {self.rc4}"


class RkCrc32(crc.Crc32Base):
	"""CRC-32/ROCKCHIP
	"""
	_names = ('CRC-32/ROCKCHIP')
	_width = 32
	_poly = 0x04c10db7
	_initvalue = 0x00000000
	_reflect_input = False
	_reflect_output = False
	_xor_output = 0


class LoaderFile():
	def __init__(self, blob):
		self.blob = blob
		offset = BOOTHEADERSIZE
		self.header = BootHeader.read(self.blob, 0)

		offset = self.header.entry471.offset
		self.entry471 = []
		for _i in range(self.header.entry471.count):
			entry = BootEntry.read(self.blob, offset)
			self.entry471.append(entry)
			offset += BOOTENTRYSIZE

		offset = self.header.entry472.offset
		self.entry472 = []
		for _i in range(self.header.entry472.count):
			entry = BootEntry.read(self.blob, offset)
			self.entry472.append(entry)
			offset += BOOTENTRYSIZE

		offset = self.header.loader.offset
		self.loader = []
		for _i in range(self.header.loader.count):
			entry = BootEntry.read(self.blob, offset)
			self.loader.append(entry)
			offset += BOOTENTRYSIZE
		crc32 = self.blob[-4:]
		calc_crc32 = RkCrc32.calc(self.blob[:-4])
		(self.crc32,) = struct.unpack("<I", crc32)
		assert self.crc32 == calc_crc32

	def entry_data(self, name, idx=0):
		entry = None
		if name == "471":
			entry = self.entry471
		elif name == "472":
			entry = self.entry472
		elif name == "loader":
			entry = self.loader
		else:
			raise LoaderFileError(f"Invalid name {name}")

		if idx > len(entry):
			raise LoaderFileError(f"Invalid index {idx}. Only has {len(entry)} entries.")
		e = entry[idx]
		logger.debug(f"{e}")
		return (self.blob[e.data_offset:e.data_offset+e.data_size], e.data_delay)

	def __str__(self):
		return f"{self.header} crc: {self.crc32:02x}"


# Manual implementation of RC4, from Wikipedia's page
# Not very secure, so don't use it elsewhere.
class rc4():
	def __init__(self):
		self.S = list(range(256))
		self.i = 0
		self.j = 0

	def ksa(self, key):
		keylength = len(key)
		self.S = list(range(256))
		j = 0
		for i in range(256):
			j = (j + self.S[i] + key[i % keylength]) % 256
			self.S[i], self.S[j] = self.S[j], self.S[i]

	def prga(self):
		self.i = (self.i + 1) % 256
		self.j = (self.j + self.S[self.i]) % 256
		self.S[self.i], self.S[self.j] = self.S[self.j], self.S[self.i]
		K = self.S[(self.S[self.i] + self.S[self.j]) % 256]
		return K

	def encrypt(self, buf):
		obuf = bytearray(len(buf))

		for offset in list(range(len(buf))):
			obuf[offset] = buf[offset] ^ self.prga()
		return obuf


def rc4_encrypt(fw_blob):

	soc_model = recovery_config["soc_model"]
	if soc_model in NEWIDB_LIST:
		return fw_blob

	# Round to 4096 block size
	blob_len = len(fw_blob)
	padded_len = (blob_len+4095)//4096 * 4096
	fw_blob = bytearray(fw_blob)
	fw_blob += bytearray([0]*(padded_len - blob_len))
	encoder = rc4()
	encoder.ksa(RC4_KEY)
	obuf = bytearray()
	for i in range(padded_len):
		obuf += encoder.encrypt(fw_blob[i*512:(i+1)*512])
	return obuf


def rockchip_run(dev, fw_name, fw_blob):

	if fw_name == 'code471':
		logger.info("Downloading code471...")
		rom = rockchip.RochipBootRom(dev)
		blob = rc4_encrypt(fw_blob)
		rom.write_blob(blob, 0x471)
	elif fw_name == 'code472':
		logger.info("Downloading code472...")
		rom = rockchip.RochipBootRom(dev)
		blob = rc4_encrypt(fw_blob)
		rom.write_blob(blob, 0x472)
	elif fw_name == "u-boot-fit":
		id = dfu.search_partid(dev, "u-boot.itb")
		if id is None:
			logger.error("Missing u-boot.itb DFU partition")
		dfu_cmd = dfu.DFU(dev, stm32=False)
		dfu_cmd.get_status()
		dfu_cmd.download_and_run(fw_blob, id, 0, len(fw_blob))
		dfu_cmd.get_status()
		dfu_cmd.detach(id)
	else:
		fw = LoaderFile(fw_blob)
		logger.info(f"{fw}")
		rom = rockchip.RochipBootRom(dev)
		for i in range(fw.header.entry471.count):
			logger.info(f"Downloading entry 471 {i}...")
			(data, delay) = fw.entry_data("471", i)
			rom.write_blob(data, 0x471)
			logger.info(f"Sleeping {delay}ms")
			time.sleep(delay / 1000)
			logger.info("Done")
		for i in range(fw.header.entry472.count):
			logger.info(f"Downloading entry 472 {i}...")
			(data, delay) = fw.entry_data("472", i)
			rom.write_blob(data, 0x472)
			logger.info(f"Sleeping {delay}ms")
			time.sleep(delay / 1000)
			logger.info("Done")
