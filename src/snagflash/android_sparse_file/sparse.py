# Copyright 2025 Collabora Ltd.
#
# SPDX-License-Identifier: GPL-2.0+
#
# Author: Arnaud Patard <arnaud.patard@collabora.com>

from snagrecover.utils import BinFileHeader
from dataclasses import dataclass

SPARSE_FILEHEADER_LEN = 28
SPARSE_CHUNKHEADER_LEN = 12
SPARSE_FILE_MAJOR = 1
SPARSE_FILE_MINOR = 0
MAGIC = 0xED26FF3A
DEFAULT_BLOCK_SIZE = 4096
CHUNK_TYPE_RAW = 0xCAC1
CHUNK_TYPE_FILL = 0xCAC2
CHUNK_TYPE_DONTCARE = 0xCAC3
CHUNK_TYPE_CRC32 = 0xCAC4


class SparseFileFormatError(Exception):
	def __init__(self, message):
		self.message = message
		super().__init__(self.message)

	def __str__(self):
		return f"Sparse file format error: {self.message}"


@dataclass
class AndroidSparseHeader(BinFileHeader):
	magic: int = MAGIC
	major: int = 1
	minor: int = 0
	header_len: int = SPARSE_FILEHEADER_LEN
	chunk_header_len: int = SPARSE_CHUNKHEADER_LEN
	block_size: int = DEFAULT_BLOCK_SIZE
	blocks: int = 0
	chunks: int = 0
	csum: int = 0

	fmt = "<IHHHHIIII"
	class_size = SPARSE_FILEHEADER_LEN

	# Size of the raw file
	def get_raw_size(self):
		return self.blocks * self.block_size

	def check(self):
		if self.magic != MAGIC:
			raise SparseFileFormatError(f"Invalid magic {self.magic}")
		if self.major != SPARSE_FILE_MAJOR or self.minor != SPARSE_FILE_MINOR:
			raise SparseFileFormatError(
				f"Invalid major or minor {self.major}.{self.minor}"
			)
		if self.header_len != SPARSE_FILEHEADER_LEN:
			raise SparseFileFormatError(
				f"Invalid header length specified in header {self.header_len}"
			)
		if self.chunk_header_len != SPARSE_CHUNKHEADER_LEN:
			raise SparseFileFormatError(
				f"Invalid chunk header length specified in header {self.chunk_header_len}"
			)
		if self.block_size % 4:
			raise SparseFileFormatError(
				f"Invalid block size {self.block_size}. Should be multiple of 4"
			)


@dataclass
class AndroidChunkHeader(BinFileHeader):
	type: int = CHUNK_TYPE_DONTCARE
	rsvd: int = 0
	size: int = 0
	total_size: int = SPARSE_CHUNKHEADER_LEN

	fmt = "<HHII"
	class_size = SPARSE_CHUNKHEADER_LEN

	def get_data_size(self, block_size):
		if self.type == CHUNK_TYPE_DONTCARE:
			return 0
		elif self.type == CHUNK_TYPE_RAW:
			return self.size * block_size
		elif self.type == CHUNK_TYPE_FILL:
			return 4
		elif self.type == CHUNK_TYPE_CRC32:
			return 4

	def check(self):
		if self.type not in [
			CHUNK_TYPE_RAW,
			CHUNK_TYPE_FILL,
			CHUNK_TYPE_DONTCARE,
			CHUNK_TYPE_CRC32,
		]:
			raise SparseFileFormatError(f"Invalid chunk type {self.type}")


class AndroidSparseFile:
	def __init__(self, read):
		self.file_header = AndroidSparseHeader()
		self.fd = None
		self.size = 0
		self.ro = read

	def open(self, fname, block_size=0):
		if self.ro is False:
			self.fd = open(fname, "wb+")
			buf = bytearray()
			AndroidSparseHeader.write(self.file_header, buf)
			self.fd.write(buf)
			self.size = SPARSE_FILEHEADER_LEN
			self.file_header.block_size = block_size
		else:
			self.fd = open(fname, "rb")
			h = self.fd.read(SPARSE_FILEHEADER_LEN)
			self.file_header = AndroidSparseHeader.read(h, 0)
			self.file_header.check()

	def close(self):
		if self.ro is False:
			self.fd.seek(0)
			buf = bytearray()
			AndroidSparseHeader.write(self.file_header, buf)
			self.fd.write(buf)
		self.fd.close()

	def read_chunk(self):
		h = self.fd.read(self.file_header.chunk_header_len)
		if not h:
			return (None, None)

		header = AndroidChunkHeader.read(h, 0)
		header.check()

		data = None
		chunk_len = header.get_data_size(self.file_header.block_size)
		if header.type == CHUNK_TYPE_FILL:
			val = self.fd.read(chunk_len)
			data = val
		elif header.type == CHUNK_TYPE_CRC32:
			val = self.fd.read(chunk_len)
			data = val
		elif header.type == CHUNK_TYPE_RAW:
			data = self.fd.read(chunk_len)
		return (header, data)

	def write_chunk(self, type, data, blocks):
		if self.ro is True:
			return
		self.size += self._write_chunk_data(type, data, blocks)
		self.file_header.chunks += 1
		self.file_header.blocks += blocks

	def _write_chunk_data(self, type, data, raw_blocks):
		header = AndroidChunkHeader()
		header.type = type
		header.total_size = SPARSE_CHUNKHEADER_LEN
		header.size = raw_blocks

		if header.type == CHUNK_TYPE_FILL:
			header.total_size += 4
		elif header.type == CHUNK_TYPE_CRC32:
			header.total_size += 4
		elif header.type == CHUNK_TYPE_RAW:
			header.total_size += len(data)
		elif header.type == CHUNK_TYPE_DONTCARE:
			data = []
		buf = bytearray()
		AndroidChunkHeader.write(header, buf)
		self.fd.write(buf)
		if len(data):
			self.fd.write(data)
		return header.total_size
