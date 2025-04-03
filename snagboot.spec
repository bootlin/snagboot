# -*- mode: python ; coding: utf-8 -*-
#
# Snagboot spec file, for PyInstaller
#

from kivy.tools.packaging.pyinstaller_hooks import get_deps_minimal, runtime_hooks
from PyInstaller.utils.hooks import copy_metadata
import packaging.requirements
import os

with open("MANIFEST.in", "r") as manifest_file:
	manifest = manifest_file.read(-1).splitlines()

snagrecover_datas = []
snagflash_datas = []
snagfactory_datas = []

# Include files listed in manifest

for line in manifest:
	if line == "":
		continue

	# remove "include "
	files = line.split(" ")[1]

	datas = None

	if files.startswith("src/snagrecover"):
		datas = snagrecover_datas
	elif files.startswith("src/snagflash"):
		datas = snagflash_datas
	elif files.startswith("src/snagfactory"):
		datas = snagfactory_datas

	files_rel = os.path.relpath(os.path.dirname(files), "src")

	datas.append((files, files_rel))

# Include package metadata from gui dependencies, so that snagfactory can find
# them at runtime with importlib

with open("src/snagfactory/gui-requirements.txt", "r") as req_file:
	gui_dependencies = req_file.read(-1).splitlines()

gui_reqs = [packaging.requirements.Requirement(req_str) for req_str in gui_dependencies]

for req in gui_reqs:
	snagfactory_datas += copy_metadata(req.name)

# Include hidden Kivy dependencies

snagfactory_deps = get_deps_minimal(video=None, audio=None)
snagfactory_deps["hiddenimports"].append("win32timezone")

snagrecover = Analysis(
	['src/snagrecover/cli.py'],
	datas=snagrecover_datas,
	optimize=0,
)

snagflash = Analysis(
	['src/snagflash/cli.py'],
	datas=snagflash_datas,
	optimize=0,
)

snagfactory = Analysis(
	['src/snagfactory/gui.py'],
	datas=snagfactory_datas,
	optimize=0,
	runtime_hooks=runtime_hooks(),
	**snagfactory_deps,
)

# Refer to snagrecover analysis for common data files

MERGE(
	(snagrecover, "snagrecover", "cli"),
	(snagflash, "snagflash", "cli"),
	(snagfactory, "snagfactory", "gui"),
)

snagrecover_exe = EXE(
	PYZ(snagrecover.pure),
	snagrecover.scripts,
	[],
	exclude_binaries=True,
	name='snagrecover',
	upx=True,
)

snagflash_exe = EXE(
	PYZ(snagflash.pure),
	snagflash.scripts,
	[],
	exclude_binaries=True,
	name='snagflash',
	upx=True,
)

snagfactory_exe = EXE(
	PYZ(snagfactory.pure),
	snagfactory.scripts,
	[],
	exclude_binaries=True,
	name='snagfactory',
	upx=True,
	console=False,
	icon="src/snagfactory/assets/lab_penguins.ico"
)

coll = COLLECT(
	snagrecover_exe,
	snagflash_exe,
	snagfactory_exe,
	snagrecover.binaries,
	snagrecover.datas,
	snagflash.binaries,
	snagflash.datas,
	snagfactory.binaries,
	snagfactory.datas,
	upx=True,
	name='snagboot',
)

