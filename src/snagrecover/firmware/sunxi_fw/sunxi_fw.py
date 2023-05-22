# This file is part of Snagboot
# Copyright (C) 2023 Bootlin
#
# Written by Romain Gantois <romain.gantois@bootlin.com> in 2023.
#
# Based on sunxi-tools (https://github.com/linux-sunxi/sunxi-tools/{fel.c,fit_image.c})
# Copyright (C) 2012  Henrik Nordstrom <henrik@henriknordstrom.net>
# Copyright (C) 2018-2020  Andre Przywara <osp@andrep.de>
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

import yaml
import os
from snagrecover.config import recovery_config
from snagrecover.protocols import memory_ops
from snagrecover.protocols import fel
from snagrecover.firmware.sunxi_fw import mmu
import logging
logger = logging.getLogger("snagrecover")
import crccheck.crc as crc
import time
import libfdt
from math import floor

UBOOT_MIN_OFFSET = 0x8000
MAX_DT_NAME_SIZE = 512

def rmr_jump(port: fel.FEL, entry_addr: int, soc_info: dict):
	logger.info(f"Entering second stage firmware using rmr request, entry point: 0x{entry_addr:x}")
	if "rvbar_addr" not in soc_info:
		raise Exception("Cannot jump to U-Boot, your soc does not have an address defined for RVBAR")
	"""
	based on linux-sunxi sunxi-fel code
	ldr		   r0, [rvbar_addr]
	ldr		   r1, [entry_addr]
	str		   r1, [r0] write entry address to RVBAR register
	dsb		   sy		data sync barrier
	isb		   sy		instruction sync barrier
	mrc		   15, 0, r0, cr12, cr0, 2 read reset management register
	orr		   r0, r0, #3 set reset request bit and aarch64 bit
	mcr		   15, 0, r0, cr12, cr0, 2 write back reset management register
	isb		   sy	   instruction sync barrier
	loop: wfi	 wait for interrupt
	b <loop>
	rvbar_addr: .word
	entry_addr: .word
	"""
	rmr_prog = b"\x24\x00\x9f\xe5"\
			+ b"\x24\x10\x9f\xe5"\
			+ b"\x00\x10\x80\xe5"\
			+ b"\x4f\xf0\x7f\xf5"\
			+ b"\x6f\xf0\x7f\xf5"\
			+ b"\x50\x0f\x1c\xee"\
			+ b"\x03\x00\x80\xe3"\
			+ b"\x50\x0f\x0c\xee"\
			+ b"\x6f\xf0\x7f\xf5"\
			+ b"\x03\xf0\x20\xe3"\
			+ b"\xfd\xff\xff\xea"\
			+ soc_info["rvbar_addr"].to_bytes(4, "little")\
			+ entry_addr.to_bytes(4, "little")
	memops = memory_ops.MemoryOps(port)
	memops.write_blob(rmr_prog, soc_info["safe_addr"], 0, len(rmr_prog))
	memops.jump(soc_info["safe_addr"])

def test_node_strprop(dt: libfdt.Fdt, node: int, prop: str, value: str) -> bool:
	prop = dt.getprop(node, prop, [libfdt.FDT_ERR_NOTFOUND])
	return prop != -1 and prop.as_str() == value

def write_node_img(port: fel.FEL, dt: libfdt.Fdt, fw_blob: bytes, node: int, dtb_addr: int = None) -> tuple:
	print(f"Downloading {dt.get_name(node)}...")
	logger.info(f"Writing FIT img node {dt.get_name(node)}")
	data_size = dt.getprop(node, "data-size", [libfdt.FDT_ERR_NOTFOUND])
	data_offset = dt.getprop(node, "data-offset", [libfdt.FDT_ERR_NOTFOUND])
	memops = memory_ops.MemoryOps(port)
	ret_size = None
	if dtb_addr is None:
		addr = dt.getprop(node, "load").as_uint32()
	else:
		addr = dtb_addr
	if data_size != -1 and data_offset != -1:
		# image is stored outside of the FIT data
		logger.debug("Image is outside FIT")
		fit_size = dt.totalsize()
		# make sure fit size is word-aligned
		if fit_size % 4 != 0:
			fit_size = 4 * floor(fit_size / 4.0) + 4
		offset = fit_size + data_offset.as_uint32()
		memops.write_blob(fw_blob, addr, offset, data_size.as_uint32())
		ret_size = data_size.as_uint32()
	elif (prop := dt.getprop(node, "data", [libfdt.FDT_ERR_NOTFOUND])) != -1:
		logger.debug("Image is inside FIT")
		data = bytes(prop)
		memops.write_blob(data, addr, 0, len(data))
		ret_size = len(data)
	else:
		logger.warning(f"Empty image {node.name}! skipping...")
	print("Done")
	return (addr, ret_size)

def write_fit(port: fel.FEL, fw_blob: bytes, dt_name: str):
	dt = libfdt.Fdt(fw_blob)
	cfgs = dt.path_offset("/configurations")
	config = None
	# search for configuration matching dt_name or default one
	if dt_name is not None:
		node = dt.first_subnode(cfgs)
		if test_node_strprop(dt, node, "description", dt_name):
			config = node
		else:
			while (node := dt.next_subnode(node, [libfdt.FDT_ERR_NOTFOUND])) != -1:
				if test_node_strprop(dt, node, "description", dt_name):
					config = node
					break
	if config is None:
		default = dt.getprop(cfgs, "default", [libfdt.FDT_ERR_NOTFOUND])
		if default != -1 and (path := dt.path_offset("/configurations/" + default.as_str(), [libfdt.FDT_ERR_NOTFOUND])) != -1:
			config = path
		else:
			raise Exception("No valid configuration node found in FIT")
	# write "firmware" and loadables
	img_paths = (dt.getprop(config, "loadables").as_stringlist()) + [dt.getprop(config, "firmware").as_str()]
	img_nodes = [dt.path_offset("/images/" + path) for path in img_paths]
	entry_addr = None
	arm64_entry = False
	dtb_addr = None
	for node in img_nodes:
		# write image
		(addr, img_size) = write_node_img(port, dt, fw_blob, node)
		if entry_addr is None and (entry := dt.getprop(node, "entry", [libfdt.FDT_ERR_NOTFOUND])) != -1:
			entry_addr = entry.as_uint32()
			entry_arch = dt.getprop(node, "arch").as_str()
			arm64_entry = entry_arch == "arm64"
		os = dt.getprop(node, "os", [libfdt.FDT_ERR_NOTFOUND])
		if os != -1 and os.as_str() == "u-boot":
			dtb_addr = addr + img_size
	if dtb_addr is None:
		logger.warning("No DTB address found")
	else:
		# write DTB after U-Boot
		dtb_node = dt.path_offset("/images/" + dt.getprop(config, "fdt").as_str())
		write_node_img(port, dt, fw_blob, dtb_node, dtb_addr = dtb_addr)
	return (entry_addr, arm64_entry)

def write_legacy(port: fel.FEL, fw_blob: bytes):
	"""
	Write U-Boot image, assuming legacy format described
	in U-Boot/include/image.h
	"""
	print("Checking checksums...")
	# check header checksum
	hdr_size = 64
	hdr_hchecksum = int.from_bytes(fw_blob[4:8], "big")
	hchecksum = crc.Crc32.calc(fw_blob[0:4] + b"\x00\x00\x00\x00" + fw_blob[8:hdr_size])
	if hdr_hchecksum != hchecksum:
		raise ValueError("Invalid header checksum in U-Boot image")
	# check data checksum
	hdr_dchecksum = int.from_bytes(fw_blob[24:28], "big")
	dchecksum = crc.Crc32.calc(fw_blob[hdr_size:])
	if hdr_dchecksum != dchecksum:
		raise ValueError("Invalid data checksum in U-Boot image")
	# write image
	size = int.from_bytes(fw_blob[12:16], "big")
	load = int.from_bytes(fw_blob[16:20], "big")
	memops = memory_ops.MemoryOps(port)
	print("Downloading file...")
	memops.write_blob(fw_blob, load, hdr_size, size)
	print("Done")
	return load

def region_intersects(start1: int, size1: int, start2: int, size2: int) -> bool:
	"""
	Check if [start2:start2+size2] and [start1:start1+size1], intersect
	"""
	if (start2 < start1) and (start2 + size2 > start1):
		return True
	elif (start2 >= start1) and (start2 < start1 + size1):
		return True
	return False

def write_spl_fragments(port: fel.FEL, fw_blob: bytes, spl_len: int, soc_info: dict) -> bytes:
	"""
	This is a bit complicated. Basically, we're
	writing SPL in RAM, but instead of overwriting the
	regions used by the boot ROM, we're writing the
	overlapping SPL chunks in backup regions, that
	will be swapped with the boot ROM regions by the
	thunk code before calling SPL (and re-swapped afterwards
	when we want to return to FEL mode. This is essentially
	the same technique than the one used by the linux-sunxi tool.
	"""
	spl_start = soc_info["spl_start"]
	spl_end = spl_start + spl_len
	spl_chunk_list = []
	# this is what we're going to write into the thunk binary so that it knows
	# what SRAM regions to swap
	overrun_regions = b""
	last_chunk = {
		"img_start": 0,
		"sram_start": spl_start,
		"size": 0,
	}
	for rom_region in soc_info["rom"]:
		overrun_regions += rom_region["start"].to_bytes(4,"little")\
				+ rom_region["backup"].to_bytes(4,"little")\
				+ rom_region["size"].to_bytes(4, "little")
		if not region_intersects(spl_start, spl_len, rom_region["start"], rom_region["size"]):
			# rom region is outside SPL so we don't have take it into account when writing SPL
			continue
		if rom_region["start"] < spl_start:
			rom_region["backup"] += spl_start - rom_region["start"]
			rom_region["start"] = spl_start
		if rom_region["start"] + rom_region["size"] > spl_end:
			rom_region["size"] =  spl_end - rom_region["start"]
		# check if backup region is clear
		if region_intersects(spl_start, spl_len, rom_region["backup"], rom_region["size"]):
			raise ValueError("Backup area for region {region} intersects with SPL's area")
		# compute SPL chunk between last ROM region and this one
		notrom_chunk = {
			"img_start": last_chunk["img_start"] + last_chunk["size"],
			"sram_start": last_chunk["sram_start"] + last_chunk["size"],
			"size": rom_region["start"] - (last_chunk["sram_start"] + last_chunk["size"])
		}
		spl_chunk_list.append(notrom_chunk)
		# compute SPL chunk corresponding to this ROM region
		rom_chunk = {
			"img_start": notrom_chunk["img_start"] + notrom_chunk["size"],
			"sram_start": notrom_chunk["sram_start"] + notrom_chunk["size"],
			"backup_start": rom_region["backup"],
			"size": rom_region["size"]
		}
		spl_chunk_list.append(rom_chunk)
		last_chunk = rom_chunk
	overrun_regions += b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
	# add rest of spl image to chunk list
	if spl_chunk_list == []:
			spl_chunk_list =  [{
				"img_start": 0,
				"sram_start": spl_start,
				"size": spl_len
			}]
	else:
		spl_chunk_list.append({
			"img_start": last_chunk["img_start"] + last_chunk["size"],
			"sram_start": last_chunk["sram_start"] + last_chunk["size"],
			"size": spl_len - (last_chunk["img_start"] + last_chunk["size"])
		})
	logger.debug(f"SPL chunk list: {spl_chunk_list}")

	# slice and download SPL according to chunk list
	memops = memory_ops.MemoryOps(port)
	for chunk in spl_chunk_list:
		if chunk["size"] == 0:
			continue
		if "backup_start" in chunk:
			# this chunk corresponds to a preserved ROM region,
			# so we write it to its backup region in SRAM
			memops.write_blob(fw_blob, chunk["backup_start"], chunk["img_start"], chunk["size"])
		else:
			memops.write_blob(fw_blob, chunk["sram_start"], chunk["img_start"], chunk["size"])
	return overrun_regions

def sunxi_spl(port: fel.FEL, fw_blob: bytes) -> tuple:
	"""
	Here we use the technique employed by the sunxi-fel tool
	from the linux-sunxi community to write SPL to SRAM without
	overwriting the BOOTROM context. They write SPL in chunks, leaving
	the important BOOTROM sections untouched. Then, they download and
	run a small assembly program called "thunk" to re-assemble SPL and
	run it. SPL will call return_to_fel when it is done. This will
	return control to thunk, which will restore the BOOTROM sections by
	swapping them with the SPL sections and give back control to the
	BOOTROM so that we can download U-Boot proper using FEL.
	You can check the linux-sunxi wiki for more details on
	this subject: https://linux-sunxi.org/FEL/USBBoot
	"""
	print("Reading SoC info...")
	with open(os.path.dirname(__file__) + "/soc_info.yaml", "r") as file:
		soc_info = yaml.safe_load(file)[recovery_config["soc_model"]]
	# check SPL header magic and checksum
	print("Checking header and checksum...")
	if fw_blob[4:12] != b"eGON.BT0":
		raise ValueError("eGON header not found at beginning of SPL image")
	hdr_checksum = 2 * int.from_bytes(fw_blob[12:16], "little") - 0x5f0a6c39
	spl_len = int.from_bytes(fw_blob[16:20], "little")
	checksum = hdr_checksum
	for word in [int.from_bytes(fw_blob[i:i+4], "little") for i in range(0, spl_len, 4)]:
		checksum = (checksum - word) % (2 ** 32)
	if checksum != 0:
		raise ValueError("Invalid checksum in SPL image")
	# try to get dt name
	dt_name = None
	if fw_blob[20:23] == [b"S", b"P", b"L"] and fw_blob[24] >= 2:
		dt_name_offset = int.from_bytes(fw_blob[32:36], "little")
		c = 0
		dt_name = bytearray()
		while c < MAX_DT_NAME_SIZE and (name_char := fw_blob[dt_name_offset + c]) != 0:
			dt_name.append(name_char)
			c += 1
		if c in [MAX_DT_NAME_SIZE, 0]:
			logger.warning("Invalid dt name, please check this SPL image's header")
		else:
			dt_name = str.decode(dt_name, "ascii")

	# for A10, A10s, A13, R8: enable L2 cache
	memops = memory_ops.MemoryOps(port)
	if recovery_config["soc_model"] in ["a10", "a10s", "a13", "r8"]:
		print("Enabling L2 cache")
		logger.info("enabling L2 cache")

		"""
		here, we are writing and reading from the
		system control coprocessor, see the armv7-a
		reference manual for more details
		mrc 15, 0, r2, cr1, cr0, 1 read ACTLR
		orr r2, r2, #2			   set bit 2
		mcr 15, 0, r2, cr1, cr0, 1 write back ACTLR
		bx	lr					   jump back to FEL
		"""
		l2_enable_prog = b"\x30\x2f\x11\xee"\
				+b"\x02\x20\x82\xe3"\
				+b"\x30\x2f\x01\xee"\
				+b"\x1e\xff\x2f\xe1"
		memops.write_blob(l2_enable_prog, soc_info["safe_addr"] , 0, len(l2_enable_prog))
		memops.jump(soc_info["safe_addr"])

	# configure MMU
	print("Disabling MMU...")
	ret = mmu.check(port, soc_info)
	mmu.disable(port, soc_info)
	must_restore_mmu = False
	if ret is not None:
		(tt, tt_addr) = ret
		must_restore_mmu = True

	# generate memory map for thunk, SPL, and bootrom sections
	if spl_len > soc_info["sram_size"]:
		raise Exception("This SPL image is too large for this SoC's SRAM")

	# check that thunk is outside SPL
	spl_start = soc_info["spl_start"]
	if region_intersects(spl_start, spl_len, soc_info["thunk"]["start"], soc_info["thunk"]["size"]):
		raise ValueError("SRAM area for thunk overlaps with SRAM area for SPL")

	print("Writing SPL fragments...")
	overrun_regions = write_spl_fragments(port, fw_blob, spl_len, soc_info)

	# copy spl load address and ROM region info into thunk binary
	with open(os.path.dirname(__file__) + "/fel-to-spl-thunk.bin", "rb") as file:
		thunk_blob = file.read(-1)

	# assemble and write thunk
	logger.debug(f"overrun regions: {overrun_regions}")
	full_thunk = thunk_blob + spl_start.to_bytes(4, "little") + overrun_regions
	print("Writing Thunk...")
	memops.write_blob(full_thunk, soc_info["thunk"]["start"], 0, len(full_thunk))

	# execute thunk
	print("Jumping to Thunk...")
	memops.jump(soc_info["thunk"]["start"])

	# apparently this delay is sometimes necessary
	time.sleep(0.5)
	# restore MMU if necessary
	if must_restore_mmu:
		print("Restoring MMU...")
		mmu.restore(port, soc_info, tt, tt_addr)

	# check return code
	h1 = memops.read32(soc_info["spl_start"] + 4).to_bytes(4, "little")
	h2 = memops.read32(soc_info["spl_start"] + 8).to_bytes(4, "little")
	if h1 + h2 != b"eGON.FEL":
		raise ValueError("Invalid return value found in SPL SRAM")
	return (spl_len, dt_name)

def sunxi_uboot(port: fel.FEL, fw_blob: bytes, dt_name: str):
	# determine image type
	magic = int.from_bytes(fw_blob[0:4], "big")
	arm64_entry = False
	if magic == 0xd00dfeed:
		(entry_addr, arm64_entry) = write_fit(port, fw_blob, dt_name)
	elif magic == 0x27051956:
		entry_addr = write_legacy(port, fw_blob)
	else:
		raise ValueError("Invalid U-Boot image format")

	print("Jumping to U-Boot...")
	if arm64_entry:
		with open(os.path.dirname(__file__) + "/soc_info.yaml", "r") as file:
			soc_info = yaml.safe_load(file)[recovery_config["soc_model"]]
		rmr_jump(port, entry_addr, soc_info)
	else:
		memops = memory_ops.MemoryOps(port)
		memops.jump(entry_addr)

def sunxi_run(port, fw_name: str, fw_blob: bytes):
	if fw_name == "spl":
		sunxi_spl(port, fw_blob)
	elif fw_name == "u-boot":
		"""
		Note that the dt name is not passed here,
		since we want to decouple the SPL and U-Boot
		images in this case, which means that we require
		a default configuration node if a FIT image is used
		"""
		sunxi_uboot(port, fw_blob, None)
	elif fw_name == "u-boot-with-spl":
		print("Running SPL stage")
		logger.info("Running SPL part of image")
		(spl_len, dt_name) = sunxi_spl(port, fw_blob)
		print("Running U-Boot stage")
		logger.info("Running U-Boot part of image")
		uboot_offset = max(spl_len, UBOOT_MIN_OFFSET)
		sunxi_uboot(port, fw_blob[uboot_offset:], dt_name)

