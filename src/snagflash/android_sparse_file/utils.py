# Copyright 2025 Collabora Ltd.
#
# SPDX-License-Identifier: GPL-2.0+
#
# Author: Arnaud Patard <arnaud.patard@collabora.com>
#
# Modified-by: Bakyaraj Moorthy <bmoorthy@qti.qualcomm.com>
#
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
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

import os
import logging

from snagflash.android_sparse_file.sparse import (
	AndroidSparseFile,
	AndroidChunkHeader,
	SPARSE_CHUNKHEADER_LEN,
	SPARSE_FILEHEADER_LEN,
	CHUNK_TYPE_DONTCARE,
	CHUNK_TYPE_RAW,
	CHUNK_TYPE_FILL,
	CHUNK_TYPE_CRC32,
)

logger = logging.getLogger("snagflash")

# Reserve space for the trailing DONT_CARE suffix chunk header
SUFFIX_RESERVE = SPARSE_CHUNKHEADER_LEN

# Human-readable names for chunk type constants, used in log messages
CHUNK_TYPE_NAMES = {
	CHUNK_TYPE_RAW: "RAW",
	CHUNK_TYPE_FILL: "FILL",
	CHUNK_TYPE_DONTCARE: "DONTCARE",
	CHUNK_TYPE_CRC32: "CRC32",
}


def chunk_type_name(chunk_type):
	"""
	Return a human-readable name for a chunk type constant, for logging.
	"""
	return CHUNK_TYPE_NAMES.get(chunk_type, f"UNKNOWN(0x{chunk_type:04X})")


class SplitFragmentState:
	"""
	Holds the accumulated state for the sparse fragment currently being built
	by split_streaming(). Using an explicit state object (instead of closures
	with 'nonlocal') keeps the helper functions below at module level and
	testable in isolation.
	"""

	def __init__(self):
		self.pending = []            # List of (chunk_type, num_blocks, payload) for current fragment
		self.pending_payload_bytes = 0  # Running sum of payload bytes in pending
		self.piece_blocks_sum = 0    # Total logical blocks covered by pending


def ensure_prefix_skip(state, blocks_done):
	"""
	Ensure current fragment starts with DONT_CARE prefix covering all
	blocks written in previous fragments.

	This maintains the logical block addressing across split files by
	inserting a DONT_CARE chunk that spans all previously written blocks.
	Only adds prefix if fragment has no content yet.

	Args:
		state: SplitFragmentState for the fragment currently being built
		blocks_done: Cumulative blocks already written across all fragments
	"""
	if state.pending:
		return  # Already has content — prefix already established
	if blocks_done > 0:
		# Insert a DONT_CARE chunk spanning all previously written blocks
		state.pending.append((CHUNK_TYPE_DONTCARE, blocks_done, None))
		state.piece_blocks_sum += blocks_done
		logger.debug(f"Added DONT_CARE prefix covering {blocks_done} blocks")


def flush_fragment(state, dest, block_size, original_total_blks):
	"""
	Serialize all staged chunks in state.pending into a complete sparse image
	fragment, append the trailing DONT_CARE suffix, write to file, and reset
	the fragment state for the next fragment.

	Each fragment is a valid sparse file that maintains the original total block count
	by padding with DONT_CARE chunks as needed.

	Args:
		state: SplitFragmentState for the fragment currently being built (reset in place)
		dest: Output path for the fragment file
		block_size: Sparse image block size in bytes
		original_total_blks: Total blocks in the original (unsplit) sparse image

	Returns:
		Path to the flushed fragment file, or None if nothing to flush.
	"""
	if not state.pending:
		return None  # Nothing to flush

	# Safety check
	if state.piece_blocks_sum > original_total_blks:
		raise IOError(
			f"Internal error: piece_blocks_sum {state.piece_blocks_sum} > "
			f"original_total_blks {original_total_blks}"
		)

	# Add DONT_CARE suffix to pad to original_total_blks
	suffix_blocks = original_total_blks - state.piece_blocks_sum
	if suffix_blocks > 0:
		state.pending.append((CHUNK_TYPE_DONTCARE, suffix_blocks, None))
		state.piece_blocks_sum += suffix_blocks
		logger.debug(f"Added DONT_CARE suffix: {suffix_blocks} blocks (total: {state.piece_blocks_sum})")

	# Serialize the fragment: file header + all chunk headers + payloads
	outf = AndroidSparseFile(False)
	outf.open(dest, block_size)

	for ctype, blks, payload in state.pending:
		chunk_bytes = blks * block_size
		logger.debug(
			f"Writing chunk: type={chunk_type_name(ctype)} "
			f"size={blks} blocks ({chunk_bytes} bytes)"
		)
		if ctype == CHUNK_TYPE_RAW:
			# RAW: chunk header + full block payload bytes
			outf.write_chunk(ctype, payload, blks)
		elif ctype == CHUNK_TYPE_FILL:
			# FILL: chunk header + 4-byte fill pattern
			outf.write_chunk(ctype, payload, blks)
		else:
			# DONT_CARE (and any future zero-payload types): header only
			outf.write_chunk(ctype, [], blks)

	outf.close()

	# Reset accumulation state for the next fragment
	state.pending = []
	state.pending_payload_bytes = 0
	state.piece_blocks_sum = 0

	return dest


def process_raw_chunk(input_fd, header, state, blocks_done, bufsize, block_size, dest, original_total_blks):
	"""
	Stage (and flush as needed) a RAW chunk, which may need to be split
	across multiple fragments since RAW payloads can be large.

	Args:
		input_fd: Input sparse file handle, positioned at the start of the chunk payload
		header: AndroidChunkHeader for this RAW chunk
		state: SplitFragmentState for the fragment currently being built
		blocks_done: Cumulative blocks already written across all fragments
		bufsize: Maximum size for each output fragment file
		block_size: Sparse image block size in bytes
		dest: Output path for fragment files
		original_total_blks: Total blocks in the original (unsplit) sparse image

	Yields:
		Path to each fragment flushed while processing this chunk
	Returns via StopIteration value: updated blocks_done
	"""
	total = header.size  # Total blocks in this RAW chunk
	off = 0              # Current block offset within this RAW chunk

	while off < total:
		ensure_prefix_skip(state, blocks_done)

		# Compute bytes already committed in this fragment (overhead)
		overhead = (
			SPARSE_FILEHEADER_LEN +
			(len(state.pending) + 1) * SPARSE_CHUNKHEADER_LEN +
			state.pending_payload_bytes +
			SUFFIX_RESERVE
		)
		avail = bufsize - overhead  # Available bytes for new RAW payload

		if avail < block_size:
			# Not enough room for even one block — flush and yield
			flushed_fragment = flush_fragment(state, dest, block_size, original_total_blks)
			if flushed_fragment:
				yield flushed_fragment
			continue  # Re-enter loop: recalculate overhead after flush

		# Determine how many blocks fit and read the matching payload
		max_blks = min(avail // block_size, total - off)

		# Read only the data we need (streaming)
		chunk_data_size = max_blks * block_size
		part = input_fd.read(chunk_data_size)

		if len(part) < chunk_data_size:
			raise IOError("Unexpected end of file while reading RAW chunk data")

		# Stage the slice as a RAW chunk in the current fragment
		state.pending.append((CHUNK_TYPE_RAW, max_blks, part))
		state.pending_payload_bytes += len(part)
		state.piece_blocks_sum += max_blks
		blocks_done += max_blks
		off += max_blks

		logger.debug(f"Staged RAW chunk: {max_blks} blocks ({total - off} remaining)")

	return blocks_done


def process_dontcare_chunk(header, state, blocks_done, bufsize, block_size, dest, original_total_blks):
	"""
	Stage a DONT_CARE chunk, flushing the current fragment first if the
	chunk header doesn't fit within bufsize.

	Returns:
		(updated blocks_done, flushed_fragment path or None)
	"""
	ensure_prefix_skip(state, blocks_done)

	# Check if adding this chunk header would exceed bufsize
	overhead = (
		SPARSE_FILEHEADER_LEN +
		(len(state.pending) + 1) * SPARSE_CHUNKHEADER_LEN +
		state.pending_payload_bytes +
		SUFFIX_RESERVE
	)

	flushed_fragment = None
	if overhead > bufsize:
		# Doesn't fit - flush current fragment
		flushed_fragment = flush_fragment(state, dest, block_size, original_total_blks)
		ensure_prefix_skip(state, blocks_done)

	# Stage DONT_CARE chunk
	state.pending.append((CHUNK_TYPE_DONTCARE, header.size, None))
	state.piece_blocks_sum += header.size
	blocks_done += header.size
	logger.debug(f"Staged DONT_CARE chunk: {header.size} blocks")

	return blocks_done, flushed_fragment


def process_fill_chunk(input_fd, header, state, blocks_done, bufsize, block_size, dest, original_total_blks):
	"""
	Stage a FILL chunk (always exactly 4 bytes of payload), flushing the
	current fragment first if it doesn't fit within bufsize.

	Returns:
		(updated blocks_done, flushed_fragment path or None)
	"""
	fill_value = input_fd.read(4)
	if len(fill_value) != 4:
		raise IOError("Truncated FILL payload")

	ensure_prefix_skip(state, blocks_done)

	# Check if adding this 4-byte payload + header fits within bufsize
	overhead = (
		SPARSE_FILEHEADER_LEN +
		(len(state.pending) + 1) * SPARSE_CHUNKHEADER_LEN +
		state.pending_payload_bytes + 4 +  # Include the 4-byte FILL payload
		SUFFIX_RESERVE
	)

	flushed_fragment = None
	if overhead > bufsize:
		# Doesn't fit - flush current fragment
		flushed_fragment = flush_fragment(state, dest, block_size, original_total_blks)
		ensure_prefix_skip(state, blocks_done)

	# Stage FILL chunk
	state.pending.append((CHUNK_TYPE_FILL, header.size, fill_value))
	state.pending_payload_bytes += 4
	state.piece_blocks_sum += header.size
	blocks_done += header.size
	logger.debug(f"Staged FILL chunk: {header.size} blocks")

	return blocks_done, flushed_fragment


def split_streaming(path, dest, bufsize):
	"""
	Generator that yields one split sparse file at a time for immediate processing.

	This streaming approach minimizes memory usage by:
	- Reading RAW chunk data incrementally (not loading entire chunk into RAM)
	- Yielding each split file immediately after creation
	- Reusing the same temporary file location
	- Proper overhead calculation accounting for all headers

	This allows processing of arbitrarily large sparse files with constant memory usage.

	Args:
		path: Path to input sparse file
		dest: Path for temporary output file (will be reused for each split)
		bufsize: Maximum size for each output file

	Yields:
		Path to each split file (same path, but content changes each iteration)
	"""
	sparse_file = AndroidSparseFile(True)
	sparse_file.open(path)

	# Store original total blocks for all output files
	original_total_blks = sparse_file.file_header.blocks
	block_size = sparse_file.file_header.block_size

	# Pre-flight validation: ensure bufsize can hold at least one block with all headers
	min_required = (
		SPARSE_FILEHEADER_LEN +      # 28 bytes: file header
		2 * SPARSE_CHUNKHEADER_LEN + # 24 bytes: prefix + one data chunk header
		block_size +                  # At least one block of data
		SPARSE_CHUNKHEADER_LEN       # 12 bytes: suffix reserve
	)
	if bufsize <= min_required:
		sparse_file.close()
		raise IOError(
			f"Buffer size {bufsize} too small. Need at least {min_required} bytes "
			f"to fit one {block_size}-byte block with headers"
		)

	# Cumulative blocks across ALL fragments so far (used for DONT_CARE prefix)
	blocks_done = 0
	state = SplitFragmentState()

	input_fd = sparse_file.fd  # Direct file handle for streaming reads

	logger.debug(f"Starting streaming split: total_blocks={original_total_blks}, block_size={block_size}")

	try:
		while True:
			# Read chunk header (not data yet)
			chunk_header_bytes = input_fd.read(SPARSE_CHUNKHEADER_LEN)
			if not chunk_header_bytes or len(chunk_header_bytes) < SPARSE_CHUNKHEADER_LEN:
				# End of input file - finalize current output
				result = flush_fragment(state, dest, block_size, original_total_blks)
				if result:
					yield result
				break

			# Parse chunk header
			header = AndroidChunkHeader.read(chunk_header_bytes, 0)
			header.check()

			logger.debug(
				f"Processing chunk: type={chunk_type_name(header.type)} "
				f"size={header.size} blocks ({header.total_size} bytes)"
			)

			if header.type == CHUNK_TYPE_RAW:
				raw_gen = process_raw_chunk(
					input_fd, header, state, blocks_done, bufsize, block_size, dest, original_total_blks
				)
				# process_raw_chunk is a generator that yields flushed fragment
				# paths and returns the updated blocks_done via StopIteration.value
				while True:
					try:
						flushed_fragment = next(raw_gen)
						yield flushed_fragment
					except StopIteration as stop:
						blocks_done = stop.value
						break

			elif header.type == CHUNK_TYPE_DONTCARE:
				blocks_done, flushed_fragment = process_dontcare_chunk(
					header, state, blocks_done, bufsize, block_size, dest, original_total_blks
				)
				if flushed_fragment:
					yield flushed_fragment

			elif header.type == CHUNK_TYPE_FILL:
				blocks_done, flushed_fragment = process_fill_chunk(
					input_fd, header, state, blocks_done, bufsize, block_size, dest, original_total_blks
				)
				if flushed_fragment:
					yield flushed_fragment

			elif header.type == CHUNK_TYPE_CRC32:
				crc_data = input_fd.read(4)
				if len(crc_data) != 4:
					raise IOError("Truncated CRC32 payload")
				logger.debug("Skipping CRC32 chunk (validation only)")
				continue

			else:
				# Unknown chunk type
				logger.warning(f"Unknown chunk type 0x{header.type:04X}, skipping")
				# Skip the data portion
				data_size = header.get_data_size(block_size)
				if data_size > 0:
					input_fd.read(data_size)

		# Final flush: emit any remaining staged chunks as the last fragment
		frag = flush_fragment(state, dest, block_size, original_total_blks)
		if frag:
			yield frag

	finally:
		sparse_file.close()