# This file is part of Snagboot
# Copyright (C) 2023 Bootlin
#
# Written by Romain Gantois <romain.gantois@bootlin.com> in 2023.
#
# Based on sunxi-tools (https://github.com/linux-sunxi/sunxi-tools/fel.c)
# Copyright (C) 2012  Henrik Nordstrom <henrik@henriknordstrom.net>
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

"""
MMU configuration steps needed to successfully
recover some SoCs.
"""
from snagrecover.protocols import fel
from snagrecover.protocols import memory_ops
import logging
logger = logging.getLogger("snagrecover")

MMU_SIZE = 0x4000
DRAM_BASE = 0x40000000
DRAM_SIZE = 0x80000000
DRAM_END = DRAM_BASE + DRAM_SIZE

def restore(port: fel.FEL, soc_info: dict, tt: bytes, tt_addr: int):
	"""
	based on linux-sunxi sunxi-fel code
	mov r0, #0
	mcr 15, 0, r0, cr8, cr7, 0	 invalidate TLB
	mcr 15, 0, r0, cr7, cr5, 0	 invalidate icache
	mcr 15, 0, r0, cr7, cr5, 6	 branch predictor invalidate all
	dsb sy data sync barrier
	isb sy instruction sync barrier
	/* Enable I-cache, MMU and branch prediction
	mrc 15, 0, r0, cr1, cr0, 0 read SCTLR
	orr r0, r0, #1 set MMU enable bit
	orr r0, r0, #0x1800 set branch prediction enable and icache enable bits
	mcr 15, 0, r0, cr1, cr0, 0 write SCTLR
	bx lr return to FEL
	"""
	restore_prog = b"\x00\x00\xa0\xe3"\
			+ b"\x17\x0f\x08\xee"\
			+ b"\x15\x0f\x07\xee"\
			+ b"\xd5\x0f\x07\xee"\
			+ b"\x4f\xf0\x7f\xf5"\
			+ b"\x6f\xf0\x7f\xf5"\
			+ b"\x10\x0f\x11\xee"\
			+ b"\x01\x00\x80\xe3"\
			+ b"\x06\x0b\x80\xe3"\
			+ b"\x10\x0f\x01\xee"\
			+ b"\x1e\xff\x2f\xe1"
	"""
	Here we modify the TT to add a few optimizations
	from the linux-sunxi community described at :
	https://github.com/linux-sunxi/sunxi-tools/commit/e4b3da2b17ee9d7c5cab9b80e708b3a309fc4c96
	"""
	tt_words = [int.from_bytes(tt[i:i+4], "little") for i in range(0, len(tt), 4)]
	for i in range(DRAM_BASE >> 20, DRAM_END >> 20):
		tt_words[i] &= ~((7 << 12) | (1 << 3) | (1 << 2))
		tt_words[i] |= 1 << 12
	tt_words[0xfff] &= ~((7 << 12) | (1 << 3) | (1 << 2))
	tt_words[0xfff] |= (1 << 12) | (1 << 3)	 | (1 << 2)

	# write MMU TT
	memops = memory_ops.MemoryOps(port)
	c = 0
	for addr in range(tt_addr, tt_addr + MMU_SIZE, 4):
		memops.write32(addr, tt_words[c])
		c += 1
	memops.write_blob(restore_prog, soc_info["safe_addr"], 0, len(restore_prog))
	memops.jump(soc_info["safe_addr"])

def check(port: fel.FEL, soc_info: dict) -> tuple:
	# if MMU was enabled by BROM, back it up
	"""
	mrc		15, 0, r0, cr1, cr0, 0 read SCTLR
	ands	r0, r0, #1			   test MMU enable bit
	beq		14 <end>			   if MMU was not enabled, return default
	mrc		15, 0, r0, cr2, cr0, 2 read TTBCR
	and		r2, r0, #7			   get TTBCR.N
	str		r2, ret2
	mrc		15, 0, r0, cr2, cr0, 0 read TTBR0
	str		r0, ret1
	end:
	bx		lr
	ret1: .word 0xcafedeca
	ret2: .word 0xcafedeca
	"""
	check_mmu = b"\x10\x0f\x11\xee"\
			+ b"\x01\x00\x10\xe2"\
			+ b"\x04\x00\x00\x0a"\
			+ b"\x50\x0f\x12\xee"\
			+ b"\x07\x20\x00\xe2"\
			+ b"\x0c\x20\x8f\xe5"\
			+ b"\x10\x0f\x12\xee"\
			+ b"\x00\x00\x8f\xe5"\
			+ b"\x1e\xff\x2f\xe1"\
			+ b"\xca\xde\xfe\xca"\
			+ b"\xca\xde\xfe\xca"
	memops = memory_ops.MemoryOps(port)
	memops.write_blob(check_mmu, soc_info["safe_addr"], 0, len(check_mmu))
	memops.jump(soc_info["safe_addr"])

	#get MMU TT or generate new one
	tt_addr_mask = (2 ** (14 - memops.read32(soc_info["safe_addr"] + len(check_mmu) - 4))) - 1
	tt_addr = memops.read32(soc_info["safe_addr"] + len(check_mmu) - 8)
	if tt_addr == 0xcafedeca:
		logger.info("MMU not enabled by ROM")
		if "tt_addr" not in soc_info:
			return None
		logger.info("Generating custom MMU translation table")
		"""
		Apparently these settings are used by the BROM
		on some SoCs.
		"""
		"""
		Based on linux-sunxi sunxi-fel code
		ldr r0, [dacr]
		mcr 15, 0, r0, cr3, cr0, {0} write DACR
		ldr r0, [ttbrc]
		mcr 15, 0, r0, cr2, cr0, 2 write TTBCR
		ldr r0, [ttbr0]
		mcr 15, 0, r0, cr2, cr0, 0 write TTBR0
		dsb sy data sync barrier
		isb sy instruction sync barrier
		bx	lr
		dacr: .word 0x55555555
		ttbrc: .word 0x00000000
		ttbr0: .word ?
		"""
		mmu_cfg_prog = b"\x1c\x00\x9f\xe5"\
				+ b"\x10\x0f\x03\xee"\
				+ b"\x18\x00\x9f\xe5"\
				+ b"\x50\x0f\x02\xee"\
				+ b"\x14\x00\x9f\xe5"\
				+ b"\x10\x0f\x02\xee"\
				+ b"\x4f\xf0\x7f\xf5"\
				+ b"\x6f\xf0\x7f\xf5"\
				+ b"\x1e\xff\x2f\xe1"\
				+ b"\x55\x55\x55\x55"\
				+ b"\x00\x00\x00\x00"\
				+ soc_info["tt_addr"].to_bytes(4, "little")
		memops.write_blob(mmu_cfg_prog, soc_info["safe_addr"], 0, len(mmu_cfg_prog))
		memops.jump(soc_info["safe_addr"])
		tt = b""
		wlist = [0x00000de2 | 0x1000] + [0x00000de2 | i << 20 for i in range(1,4095)] + [(0x00000de2 | 4095 << 20) | 0x1000]
		for w in wlist:
			tt += w.to_bytes(4, "little")
		tt_addr = soc_info["tt_addr"]
		return (tt, tt_addr)
	if tt_addr & tt_addr_mask != 0:
		raise ValueError(f"Invalid MMU TT address 0x{tt_addr:x} with alignment mask 0x{tt_addr_mask:x}")
	logger.debug(f"MMU TT address 0x{tt_addr:x} alignment mask 0x{tt_addr_mask:x}")
	tt_barr = bytearray()
	for addr in range(tt_addr, tt_addr + MMU_SIZE, 4):
		entry = memops.read32(addr)
		# check MMU entry
		if (entry >> 1) & 1 != 1 or (entry >> 18) & 1 != 0 or (entry >> 20) != (addr - tt_addr) // 4:
			raise ValueError(f"Not a valid MMU TT entry 0x{entry:x}")
		tt_barr += entry.to_bytes(4, "little")
	tt = bytes(tt_barr)
	return (tt, tt_addr)

def disable(port: fel.FEL, soc_info: dict):
	"""
	based on linux-sunxi sunxi-fel code
	mrc 15, 0, r0, cr1, cr0, 0	read SCTLR
	bic r0, r0, #1				clear MMU enable bit
	bic r0, r0, #0x1800			clear branch prediction enable bit and Instruction cache enable bit
	mcr 15, 0, r0, cr1, cr0, 0	write back SCTLR
	bx	lr						return back to FEL
	"""
	logger.info("disabling MMU...")
	mmu_prog = b"\x10\x0f\x11\xee"\
			+ b"\x01\x00\xc0\xe3"\
			+ b"\x06\x0b\xc0\xe3"\
			+ b"\x10\x0f\x01\xee"\
			+ b"\x1e\xff\x2f\xe1"
	memops = memory_ops.MemoryOps(port)
	memops.write_blob(mmu_prog, soc_info["safe_addr"], 0, len(mmu_prog))
	memops.jump(soc_info["safe_addr"])

