# This file is part of Snagboot
# Copyright (C) 2026 Bootlin
#
# Written by Romain Gantois <romain.gantois@bootlin.com> in 2026.
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
#

from snagrecover.utils import BinFileHeader, dnload_iter
from dataclasses import dataclass
from math import floor
import logging

logger = logging.getLogger("snagrecover")

import re

FAT_ATTR_READ_ONLY = 1
FAT_ATTR_HIDDEN = 2
FAT_ATTR_SYSTEM = 4
FAT_ATTR_VOLUME_ID = 8
FAT_ATTR_DIRECTORY = 16
FAT_ATTR_ARCHIVE = 32

FAT_ATTR_LONG_NAME = (
	FAT_ATTR_READ_ONLY | FAT_ATTR_HIDDEN | FAT_ATTR_SYSTEM | FAT_ATTR_VOLUME_ID
)

FAT_LAST_LONG_ENTRY = 0x40

FAT_DIRENT_SIZE = 32
DIRENT_NAME_SIZE = 11


@dataclass
class BPB(BinFileHeader):
	jmpBoot: bytes
	OEMName: bytes
	BytsPerSec: int
	SecPerClus: int
	RsvdSecCnt: int
	NumFATs: int
	RootEntCnt: int
	TotSec16: int
	Media: bytes
	FATSz16: int
	SecPerTrk: int
	NumHeads: int
	HiddSec: int
	TotSec32: int

	fmt = "<3s8sHBHBHHcHHHLL"
	class_size = 36


@dataclass
class BPB32Tail(BinFileHeader):
	FATSz32: int
	ExtFlags: bytes
	FSVer: bytes
	RootClus: int
	FSInfo: int

	fmt = "<L2s2sLH"
	class_size = 14


@dataclass
class FATDirent(BinFileHeader):
	Name: bytes
	Attr: int
	NTRes: bytes
	CrtTimeTenth: int
	CrtTime: int
	CrtDate: int
	LstAccDate: int
	FstClusHI: int
	WrtTime: int
	WrtDate: int
	FstClusLO: int
	FileSize: int

	fmt = "<11sBcBHHHHHHHL"
	class_size = FAT_DIRENT_SIZE


@dataclass
class FATLongDirent(BinFileHeader):
	Ord: int
	Name1: bytes
	Attr: int
	Type: int
	Chksum: int
	Name2: bytes
	FstClusLO: int
	Name3: bytes

	fmt = "<B10sBBB12sH4s"
	class_size = FAT_DIRENT_SIZE


class FATFileEntry:
	def __init__(
		self, dirent: FATDirent, dirent_start: int, num_dirents: int, name: str
	):
		self.dirent = dirent
		self.dirent_start = dirent_start
		self.num_dirents = num_dirents
		self.name = name

		self.last_dirent_pos = self.dirent_start + num_dirents * FAT_DIRENT_SIZE

	def name_matches(self, name: str):
		return self.name.lower() == name.lower()

	def set_first_cluster(self, cluster: int):
		self.dirent.FstClusHI = (cluster >> 16) & 0xFFFF
		self.dirent.FstClusLO = cluster & 0xFFFF


def file_name_is_8_3(name: str):
	"""
	This probably has some false-negatives, but it works for our purposes.
	"""
	pattern = re.compile(r"^[\w\-]{1,8}(\.[\w\-]{1,3})?$")

	return pattern.match(name) is not None


def dirent_sub_name(dirent: FATDirent) -> tuple:
	name = None
	name_ord = 0

	if dirent.Attr == FAT_ATTR_LONG_NAME:
		dirent_bytes = bytearray()
		FATDirent.write(dirent, dirent_bytes)

		l_dirent = FATLongDirent.read(dirent_bytes)

		name = l_dirent.Name1 + l_dirent.Name2 + l_dirent.Name3
		name_ord = l_dirent.Ord
	else:
		if bytes(dirent.Name[0]) == b"\x05":
			name = chr(b"\xe5") + dirent.Name[1:]
		else:
			name = dirent.Name

	return (name, name_ord)


def dirent_is_free(dirent: FATDirent) -> bool:
	return dirent.Name[0:1] in [b"\x00", b"\xe5"]


def is_last_dirent(dirent: FATDirent) -> bool:
	return dirent.Name[0] == 0


def dirent_has_attr(dirent: FATDirent, attr: int) -> bool:
	return dirent.Attr & attr == attr


class FAT:
	"""
	A minimal subset of FAT filesystem support. Handles creation and
	deletion of top-level regular files.
	"""

	def __init__(self, path: str, offset: int):
		self.fs = open(path, "rb+")
		self.offset = offset
		self.bpb = BPB.read(self.read_bytes(0, 36))
		self.bpb_tail = BPB32Tail.read(self.read_bytes(36, 14))

		if self.bpb.TotSec16 != 0:
			tot_sec = self.bpb.TotSec16
		else:
			tot_sec = self.bpb.TotSec32

		data_sec = tot_sec - self.cluster_2_first_sector()

		self.count_of_clusters = floor(data_sec / self.bpb.SecPerClus)

		if self.count_of_clusters < 4085:
			self.fat_type = 12
		elif self.count_of_clusters < 65525:
			self.fat_type = 16
		else:
			self.fat_type = 32

		logger.debug(f"FAT{self.fat_type} filesystem at {path}")

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		self.fs.close()

	def fat_eoc_value(self) -> bytes:
		if self.fat_type == 12:
			return 0xFF8
		elif self.fat_type == 16:
			return 0xFFF8
		else:
			return 0x0FFFFFF8

	def fat_entry_is_eoc(self, fat: int):
		return fat >= self.fat_eoc_value()

	def get_fat_sz(self) -> int:
		if self.bpb.FATSz16 != 0:
			return self.bpb.FATSz16

		return self.bpb_tail.FATSz32

	def sec_to_bytes(self, sectors) -> int:
		return sectors * self.bpb.BytsPerSec

	def bytes_to_sec(self, b: int) -> float:
		return float(b) / self.bpb.BytsPerSec

	def root_dir_sectors(self) -> int:
		return floor(
			self.bytes_to_sec(
				self.bpb.RootEntCnt * FAT_DIRENT_SIZE + self.sec_to_bytes(1) - 1
			)
		)

	def cluster_2_first_sector(self) -> int:
		root_dir_sec = self.root_dir_sectors()

		fat_sz = self.get_fat_sz()

		return self.bpb.RsvdSecCnt + self.bpb.NumFATs * fat_sz + root_dir_sec

	def first_root_dir_sec(self) -> int:
		if self.fat_type in [12, 16]:
			return self.bpb.RsvdSecCnt + self.bpb.NumFATs * self.bpb.FATSz16
		else:
			return self.cluster_n_first_sector(self.bpb_tail.RootClus)

	#### I/O on self.fs BEGIN ####

	"""
	Note: Methods in this section may change the stream position of self.fs.
	"""

	def read_bytes(self, start, size) -> bytes:
		self.fs.seek(self.offset + start)

		return self.fs.read(size)

	def write_bytes(self, start, data: bytes):
		self.fs.seek(self.offset + start)

		return self.fs.write(data)

	def read_sectors(self, start_sc, size_sc) -> bytes:
		return self.read_bytes(self.sec_to_bytes(start_sc), self.sec_to_bytes(size_sc))

	#### I/O on self.fs END ####

	def get_dirent_long_name(self, dirent: FATDirent, dirent_pos: int) -> str:
		num_dirents = 1
		name, name_ord = dirent_sub_name(dirent)

		assert name_ord & FAT_LAST_LONG_ENTRY == FAT_LAST_LONG_ENTRY

		name_ord &= ~FAT_LAST_LONG_ENTRY
		nul_term = 0
		while nul_term < len(name):
			if name[nul_term : nul_term + 2] == b"\x00\x00":
				name = name[:nul_term]
				break
			nul_term += 2

		name_dirent_pos = dirent_pos + FAT_DIRENT_SIZE

		while name_ord > 1:
			dirent_bytes = self.read_bytes(name_dirent_pos, FAT_DIRENT_SIZE)
			dirent = FATDirent.read(dirent_bytes)
			sub_name, new_name_ord = dirent_sub_name(dirent)

			assert new_name_ord == name_ord - 1
			name_ord = new_name_ord

			name = sub_name + name

			num_dirents += 1
			name_dirent_pos += FAT_DIRENT_SIZE

		return name.decode("utf-16"), num_dirents

	def get_file_entry(self, dirent_pos: int) -> tuple:
		dirent_bytes = self.read_bytes(dirent_pos, FAT_DIRENT_SIZE)
		dirent = FATDirent.read(dirent_bytes)

		if dirent_is_free(dirent):
			return FATFileEntry(dirent, dirent_pos, 1, None)

		if dirent.Attr & FAT_ATTR_LONG_NAME != FAT_ATTR_LONG_NAME:
			name = dirent.Name[0:8].decode("ascii").rstrip(" ")
			ext = dirent.Name[8:].decode("ascii").rstrip(" ")

			if ext != "":
				name += f".{ext}"

			return FATFileEntry(dirent, dirent_pos, 1, name)

		long_name, num_name_dirents = self.get_dirent_long_name(dirent, dirent_pos)

		dirent_bytes = self.read_bytes(
			dirent_pos + FAT_DIRENT_SIZE * num_name_dirents, FAT_DIRENT_SIZE
		)
		return FATFileEntry(
			FATDirent.read(dirent_bytes), dirent_pos, 1 + num_name_dirents, long_name
		)

	def write_file_entry(self, f_entry: FATFileEntry):
		if f_entry.num_dirents > 1:
			raise ValueError("Cannot write file entry: contains more than one dirent")

		dirent = f_entry.dirent
		if len(dirent.Name) < DIRENT_NAME_SIZE:
			dirent.Name += b"\x00" * (DIRENT_NAME_SIZE - len(dirent.Name))

		buf = bytearray()
		FATDirent.write(dirent, buf)

		self.write_bytes(f_entry.dirent_start, buf)

	def free_dirent(self, dirent_pos: int):
		dirent_bytes = bytearray(self.read_bytes(dirent_pos, FAT_DIRENT_SIZE))

		dirent = FATDirent.read(dirent_bytes)

		if dirent.Attr & FAT_ATTR_LONG_NAME != FAT_ATTR_LONG_NAME:
			clusters = self.get_clusters(dirent)
			for cluster in clusters:
				self.write_cluster_fat(cluster, 0)

		dirent.Name = b"\xe5"

		FATDirent.write(dirent, dirent_bytes)

		self.write_bytes(dirent_pos, dirent_bytes)

	def walk_root_dir(self):
		dirent_pos = self.sec_to_bytes(self.first_root_dir_sec())
		entries = []

		f_entry = self.get_file_entry(dirent_pos)
		if is_last_dirent(f_entry.dirent):
			return entries

		if not dirent_is_free(f_entry.dirent):
			entries.append(f_entry)

		dirent_pos += f_entry.num_dirents * FAT_DIRENT_SIZE

		while True:
			f_entry = self.get_file_entry(dirent_pos)
			dirent_pos += f_entry.num_dirents * FAT_DIRENT_SIZE

			if is_last_dirent(f_entry.dirent):
				break

			if dirent_is_free(f_entry.dirent):
				continue

			entries.append(f_entry)

		return entries

	def list_files(self) -> list:
		return [f_entry.name for f_entry in self.walk_root_dir()]

	def find_free_entry(self) -> FATFileEntry:
		dirent_pos = self.sec_to_bytes(self.first_root_dir_sec())
		max_root_dirents = floor(
			self.sec_to_bytes(self.root_dir_sectors()) / FAT_DIRENT_SIZE
		)

		dirent_index = 0

		while dirent_index < max_root_dirents:
			f_entry = self.get_file_entry(dirent_pos)

			if is_last_dirent(f_entry.dirent):
				# Mark next dirent as last dirent
				next_f_entry = self.get_file_entry(dirent_pos + FAT_DIRENT_SIZE)
				next_f_entry.dirent.Name = b"\x00"

				self.write_file_entry(next_f_entry)

				return f_entry

			if dirent_is_free(f_entry.dirent):
				return f_entry

			dirent_pos += f_entry.num_dirents * FAT_DIRENT_SIZE

		return None

	def cluster_n_first_sector(self, n: int) -> int:
		return (n - 2) * self.bpb.SecPerClus + self.cluster_2_first_sector()

	def cluster_n_fat_offset(self, n: int) -> int:
		if self.fat_type == 16:
			fat_offset = n * 2
		elif self.fat_type == 32:
			fat_offset = n * 4
		else:
			fat_offset = n + floor(n / 2)

		return self.sec_to_bytes(self.bpb.RsvdSecCnt) + fat_offset

	def get_cluster_fat(self, cluster) -> int:
		fat_offset = self.cluster_n_fat_offset(cluster)

		if self.fat_type == 16:
			fat_bytes = self.read_bytes(fat_offset, 2)
		elif self.fat_type == 32:
			fat_bytes = self.read_bytes(fat_offset, 4)
		else:
			fat_bytes = self.read_bytes(fat_offset, 2)

		fat = int.from_bytes(fat_bytes, "little")

		if self.fat_type == 32:
			fat &= 0x0FFFFFFF
		elif self.fat_type == 12:
			if cluster % 2 == 0:
				fat &= 0x0FFF
			else:
				fat >>= 4

		return fat

	def write_cluster(self, cluster: int, data: bytes):
		assert len(data) <= self.bpb.BytsPerSec * self.bpb.SecPerClus

		sector = self.cluster_n_first_sector(cluster)
		self.write_bytes(self.sec_to_bytes(sector), data)

	def write_cluster_fat(self, cluster: int, fat: int):
		fat_offset = self.cluster_n_fat_offset(cluster)

		if self.fat_type == 16:
			assert fat & 0xFFFF == fat

			fat_bytes = int.to_bytes(fat, 2, "little")
		elif self.fat_type == 32:
			assert fat & 0x0FFFFFFF == fat

			prev_fat = int.from_bytes(self.read_bytes(fat_offset, 4), "little")
			fat_bytes = int.to_bytes(fat | (prev_fat & 0xF0000000), 4, "little")
		else:
			assert fat & 0x0FFF == fat

			prev_fat = int.from_bytes(self.read_bytes(fat_offset, 2), "little")

			if cluster % 2 == 0:
				fat_bytes = int.to_bytes(fat | (prev_fat & 0xF000), 2, "little")
			else:
				fat_bytes = int.to_bytes((fat << 4) | (prev_fat & 0xF), 2, "little")

		self.write_bytes(fat_offset, fat_bytes)

	def get_clusters(self, dirent) -> int:
		clusters = []

		first_cluster = (dirent.FstClusHI << 16) | dirent.FstClusLO

		clusters.append(first_cluster)

		fat_entry = self.get_cluster_fat(first_cluster)

		while not self.fat_entry_is_eoc(fat_entry):
			clusters.append(fat_entry)

			fat_entry = self.get_cluster_fat(fat_entry)

		return clusters

	def find_free_cluster(self):
		cluster = 2

		while cluster < self.count_of_clusters:
			if self.get_cluster_fat(cluster) == 0:
				return cluster

			cluster += 1

	def mark_cluster_eoc(self, cluster: int):
		self.write_cluster_fat(cluster, self.fat_eoc_value())

	def append_cluster(self, end_of_chain: int, next_cluster: int):
		self.write_cluster_fat(end_of_chain, next_cluster)

	def delete_file(self, name: str):
		if not self.file_exists(name):
			return

		f_entry = self.find_file_entry(name)

		for dirent_i in range(f_entry.num_dirents):
			self.free_dirent(f_entry.dirent_start + dirent_i * FAT_DIRENT_SIZE)

	def create_file(self, name: str, data: bytes):
		if self.file_exists(name):
			raise ValueError(f"Cannot create file {name}, file exists!")

		# Creating files with long names isn't supported
		if not file_name_is_8_3(name):
			raise ValueError(
				f"Cannot create file with name: {name}, only 8.3 file names are supported)"
			)

		f_entry = self.find_free_entry()

		if f_entry is None:
			raise ValueError(
				"Failed to find a free FAT root directory entry, no space left!"
			)

		f_name, dot, ext = name.partition(".")

		f_entry.dirent.Attr = 0
		f_entry.dirent.Name = (f"{f_name:<8}" + f"{ext:<3}").encode("ascii")
		f_entry.dirent.FileSize = len(data)
		f_entry.dirent.NTRes = b"\x00"

		end_of_chain = None

		for chunk in dnload_iter(data, self.bpb.BytsPerSec * self.bpb.SecPerClus):
			cluster = self.find_free_cluster()
			if cluster is None:
				raise ValueError(
					f"Failed to find a free FAT cluster to create {name}, no space left!"
				)

			if end_of_chain is None:
				f_entry.set_first_cluster(cluster)
				self.mark_cluster_eoc(cluster)
				end_of_chain = cluster
			else:
				self.append_cluster(end_of_chain, cluster)
				self.mark_cluster_eoc(cluster)

			self.write_cluster(cluster, chunk)
			end_of_chain = cluster

		self.write_file_entry(f_entry)

	def file_exists(self, name):
		return any([f_entry.name_matches(name) for f_entry in self.walk_root_dir()])

	def get_file_size(self, name):
		dirent = None

		for f_entry in self.walk_root_dir():
			if f_entry.name_matches(name):
				dirent = f_entry.dirent
				break

		if dirent is None:
			raise ValueError(f"File {name} not found")

		return dirent.FileSize

	def find_file_entry(self, name: str):
		for f_entry in self.walk_root_dir():
			if f_entry.name_matches(name):
				return f_entry

		raise ValueError(f"File {name} not found")

	def read_file(self, name):
		f_entry = self.find_file_entry(name)
		dirent = f_entry.dirent

		data = bytearray()
		left = dirent.FileSize

		clusters = self.get_clusters(dirent)

		for cluster in clusters:
			sector = self.cluster_n_first_sector(cluster)

			new_data = self.read_bytes(
				self.sec_to_bytes(sector),
				min(left, self.sec_to_bytes(self.bpb.SecPerClus)),
			)

			left -= len(new_data)
			data += bytearray(new_data)

		return data
