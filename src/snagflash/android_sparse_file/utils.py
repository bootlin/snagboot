# Copyright 2025 Collabora Ltd.
#
# SPDX-License-Identifier: GPL-2.0+
#
# Author: Arnaud Patard <arnaud.patard@collabora.com>

import os

from snagflash.android_sparse_file.sparse import (
	AndroidSparseFile,
	SPARSE_CHUNKHEADER_LEN,
	CHUNK_TYPE_DONTCARE,
	CHUNK_TYPE_RAW,
)


def split(path, dest, bufsize):
	flist = []
	sparse_file = AndroidSparseFile(True)
	sparse_file.open(path)
	split_count = 0

	outf = AndroidSparseFile(False)
	(root, ext) = os.path.splitext(dest)
	new_fname = f"{root}{split_count}{ext}"
	outf.open(new_fname, sparse_file.file_header.block_size)
	flist.append(new_fname)

	while True:
		(header, data) = sparse_file.read_chunk()
		if header is None:
			outf.close()
			break
		rem_space = bufsize - outf.size
		if header.total_size > rem_space:
			split_blocks = int(rem_space / outf.file_header.block_size)
			split = split_blocks * outf.file_header.block_size
			rem = header.total_size - split - SPARSE_CHUNKHEADER_LEN
			rem_blocks = int(rem / outf.file_header.block_size)
			# non RAW chunks. can't split them.
			if header.type != CHUNK_TYPE_RAW:
				split = 0
				rem = header.total_size
			else:
				outf.write_chunk(header.type, data[0:split], split_blocks)
			written_blocks = outf.file_header.blocks
			outf.close()
			split_count += 1

			outf = AndroidSparseFile(False)
			new_fname = f"{root}{split_count}{ext}"
			outf.open(new_fname, sparse_file.file_header.block_size)
			flist.append(new_fname)
			outf.write_chunk(CHUNK_TYPE_DONTCARE, [], written_blocks)
			outf.write_chunk(header.type, data[split:], rem_blocks)

			continue
		outf.write_chunk(header.type, data, header.size)

	sparse_file.close()

	return flist
