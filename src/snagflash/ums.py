# This file is part of Snagboot
# Copyright (C) 2023 Bootlin
#
# Written by Romain Gantois <romain.gantois@bootlin.com> in 2023.
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
from snagflash.utils import int_arg
import shutil
import tempfile
from snagflash.bmaptools import BmapCreate
from snagflash.bmaptools import BmapCopy
import sys
import time

FILEPATH_RETRIES = 5

def wait_filepath(path: str):
	print(f"Waiting for {path}...")
	retries = 0
	while not os.path.exists(path):
		if retries >= FILEPATH_RETRIES:
			print(f"Timeout: file or directory {path} does not exist", file=sys.stderr)
			sys.exit(-1)
		time.sleep(2)
		print(f"Retrying: find {path} {retries}/{FILEPATH_RETRIES}")
		retries += 1
	print("Done")

def bmap_copy(filepath: str, dev, src_size: int):
	mappath = os.path.splitext(filepath)[0] + ".bmap"
	mapfile = None
	print(f"Looking for {mappath}...")
	gen_bmap = True
	if os.path.exists(mappath):
		print(f"Found bmap file {mappath}")
		gen_bmap = False
		mapfileb = open(mappath, "rb")
		# check if the bmap file is clearsigned
		# if it is, we shouldn't handle it, since
		# I'd prefer to avoid depending on the gpg package
		hdr = mapfileb.read(34)
		if hdr == b"-----BEGIN PGP SIGNED MESSAGE-----":
			print("Warning: bmap file is clearsigned, skipping...")
			gen_bmap = True
		else:
			mapfileb.seek(0)
	if gen_bmap:
		print("Generating bmap...")
		try:
			mapfile = tempfile.NamedTemporaryFile("w+")
		except IOError as err:
			raise Exception("Could not create temporary file for bmap") from err
		mapfile.flush()
		mapfile.seek(0)
		creator = BmapCreate.BmapCreate(filepath, mapfile, "sha256")
		creator.generate(True)
		mapfileb = open(mapfile.name, "rb")

	with open(filepath, "rb") as src_file:
		writer = BmapCopy.BmapBdevCopy(src_file, dev, mapfileb, src_size)
		writer.copy(False, True)
	mapfileb.close()
	if mapfile is not None:
		mapfile.close()

def write_raw(args):
	devpath = args.blockdev
	filepath = args.src
	wait_filepath(devpath)
	if not os.path.exists(filepath):
		print(f"File {filepath} does not exist", file=sys.stderr)
		sys.exit(-1)
	print(f"Reading {filepath}...")
	with open(filepath, "rb") as file:
		blob = file.read(-1)
	if args.size is not None:
		size = int_arg(args.size)
	else:
		size = len(blob)
	print(f"Copying {size} bytes of {filepath} to {devpath}...")
	with open(devpath, "rb+") as dev:
		bmap_copy(filepath, dev, size)
	print("Done")

def ums(args):
	if args.dest:
		if os.path.isdir(args.dest):
			wait_filepath(args.dest)
			print(f"Copying {args.src} to {args.dest}/{os.path.basename(args.src)}...")
		else:
			dirname = os.path.dirname(args.dest)
			if dirname != "":
				wait_filepath(dirname)
			print(f"Copying {args.src} to {args.dest}...")
		shutil.copy(args.src, args.dest)
		print("Done")
	if args.blockdev:
		write_raw(args)


