# Copyright 2025 Collabora Ltd.
#
# SPDX-License-Identifier: GPL-2.0+
#
# Author: Arnaud Patard <arnaud.patard@collabora.com>
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
	SPARSE_CHUNKHEADER_LEN,
	SPARSE_FILEHEADER_LEN,
	CHUNK_TYPE_DONTCARE,
	CHUNK_TYPE_RAW,
	CHUNK_TYPE_FILL,
	CHUNK_TYPE_CRC32,
)

logger = logging.getLogger("snagflash")


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

	# Block accounting variables for tracking fragment state
	blocks_done = 0              # Cumulative blocks across ALL fragments (for prefix)
	pending = []                 # List of (chunk_type, num_blocks, payload) for current fragment
	pending_payload_bytes = 0    # Running sum of payload bytes in pending
	piece_blocks_sum = 0         # Total logical blocks covered by pending

	input_fd = sparse_file.fd  # Direct file handle for streaming reads

	logger.debug(f"Starting streaming split: total_blocks={original_total_blks}, block_size={block_size}")

	# Reserve space for the trailing DONT_CARE suffix chunk header
	_SUFFIX_RESERVE = SPARSE_CHUNKHEADER_LEN

	def ensure_prefix_skip():
		"""
		Ensure current fragment starts with DONT_CARE prefix covering all
		blocks written in previous fragments.

		This maintains the logical block addressing across split files by
		inserting a DONT_CARE chunk that spans all previously written blocks.
		Only adds prefix if fragment has no content yet.
		"""
		nonlocal pending, piece_blocks_sum
		if pending:
			return  # Already has content — prefix already established
		if blocks_done > 0:
			# Insert a DONT_CARE chunk spanning all previously written blocks
			pending.append((CHUNK_TYPE_DONTCARE, blocks_done, None))
			piece_blocks_sum += blocks_done
			logger.debug(f"Added DONT_CARE prefix covering {blocks_done} blocks")

	def flush():
		"""
		Serialize all staged chunks in 'pending' into a complete sparse image fragment,
		append the trailing DONT_CARE suffix, write to file, and reset state.

		Each fragment is a valid sparse file that maintains the original total block count
		by padding with DONT_CARE chunks as needed.

		Returns the path to the flushed fragment file, or None if nothing to flush.
		"""
		nonlocal pending, pending_payload_bytes, piece_blocks_sum

		if not pending:
			return None  # Nothing to flush

		# Safety check
		if piece_blocks_sum > original_total_blks:
			raise IOError(
				f"Internal error: piece_blocks_sum {piece_blocks_sum} > "
				f"original_total_blks {original_total_blks}"
			)

		# Add DONT_CARE suffix to pad to original_total_blks
		suffix_blocks = original_total_blks - piece_blocks_sum
		if suffix_blocks > 0:
			pending.append((CHUNK_TYPE_DONTCARE, suffix_blocks, None))
			piece_blocks_sum += suffix_blocks
			logger.debug(f"Added DONT_CARE suffix: {suffix_blocks} blocks (total: {piece_blocks_sum})")

		# Serialize the fragment: file header + all chunk headers + payloads
		outf = AndroidSparseFile(False)
		outf.open(dest, block_size)

		for ctype, blks, payload in pending:
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
		pending = []
		pending_payload_bytes = 0
		piece_blocks_sum = 0

		return dest

	try:
		while True:
			# Read chunk header (not data yet)
			chunk_header_bytes = input_fd.read(SPARSE_CHUNKHEADER_LEN)
			if not chunk_header_bytes or len(chunk_header_bytes) < SPARSE_CHUNKHEADER_LEN:
				# End of input file - finalize current output
				result = flush()
				if result:
					yield result
				break

			# Parse chunk header
			from snagflash.android_sparse_file.sparse import AndroidChunkHeader
			header = AndroidChunkHeader.read(chunk_header_bytes, 0)
			header.check()

			logger.debug(f"Processing chunk: type=0x{header.type:04X}, blocks={header.size}, total_size={header.total_size}")

			if header.type == CHUNK_TYPE_RAW:
				# RAW chunk handling: may need to be split across multiple fragments
				# since RAW payloads can be large
				total = header.size  # Total blocks in this RAW chunk
				off = 0              # Current block offset within this RAW chunk

				while off < total:
					ensure_prefix_skip()

					# Compute bytes already committed in this fragment (overhead)
					overhead = (
						SPARSE_FILEHEADER_LEN +
						(len(pending) + 1) * SPARSE_CHUNKHEADER_LEN +
						pending_payload_bytes +
						_SUFFIX_RESERVE
					)
					avail = bufsize - overhead  # Available bytes for new RAW payload

					if avail < block_size:
						# Not enough room for even one block — flush and yield
						frag = flush()
						if frag:
							yield frag
						continue  # Re-enter loop: recalculate overhead after flush

					# Determine how many blocks fit and read the matching payload
					max_blks = min(avail // block_size, total - off)

					# Read only the data we need (streaming)
					chunk_data_size = max_blks * block_size
					part = input_fd.read(chunk_data_size)

					if len(part) < chunk_data_size:
						raise IOError(f"Unexpected end of file while reading RAW chunk data")

					# Stage the slice as a RAW chunk in the current fragment
					pending.append((CHUNK_TYPE_RAW, max_blks, part))
					pending_payload_bytes += len(part)
					piece_blocks_sum += max_blks
					blocks_done += max_blks
					off += max_blks

					logger.debug(f"Staged RAW chunk: {max_blks} blocks ({total - off} remaining)")

			elif header.type == CHUNK_TYPE_DONTCARE:
				# DONT_CARE chunk handling: no payload (0 bytes), so we only need
				# to check whether the additional 12-byte chunk header fits
				ensure_prefix_skip()

				# Check if adding this chunk header would exceed bufsize
				overhead = (
					SPARSE_FILEHEADER_LEN +
					(len(pending) + 1) * SPARSE_CHUNKHEADER_LEN +
					pending_payload_bytes +
					_SUFFIX_RESERVE
				)

				if overhead > bufsize:
					# Doesn't fit - flush current fragment
					frag = flush()
					if frag:
						yield frag
					ensure_prefix_skip()

				# Stage DONT_CARE chunk
				pending.append((CHUNK_TYPE_DONTCARE, header.size, None))
				piece_blocks_sum += header.size
				blocks_done += header.size
				logger.debug(f"Staged DONT_CARE chunk: {header.size} blocks")

			elif header.type == CHUNK_TYPE_FILL:
				# FILL chunk handling: payload is always exactly 4 bytes (the repeating pattern)
				fill_value = input_fd.read(4)
				if len(fill_value) != 4:
					raise IOError("Truncated FILL payload")

				ensure_prefix_skip()

				# Check if adding this 4-byte payload + header fits within bufsize
				overhead = (
					SPARSE_FILEHEADER_LEN +
					(len(pending) + 1) * SPARSE_CHUNKHEADER_LEN +
					pending_payload_bytes + 4 +  # Include the 4-byte FILL payload
					_SUFFIX_RESERVE
				)

				if overhead > bufsize:
					# Doesn't fit - flush current fragment
					frag = flush()
					if frag:
						yield frag
					ensure_prefix_skip()

				# Stage FILL chunk
				pending.append((CHUNK_TYPE_FILL, header.size, fill_value))
				pending_payload_bytes += 4
				piece_blocks_sum += header.size
				blocks_done += header.size
				logger.debug(f"Staged FILL chunk: {header.size} blocks")

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
		frag = flush()
		if frag:
			yield frag

	finally:
		sparse_file.close()
