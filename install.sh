#!/bin/env sh

PACKAGE_VERSION_PATTERN='([1-9][0-9]*!)?(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*((a|b|rc)(0|[1-9][0-9]*))?(\.post(0|[1-9][0-9]*))?(\.dev(0|[1-9][0-9]*))?'
VENV=$(python3 -c "import sys;print(sys.prefix != sys.base_prefix)")
EXTRA=""
if [ "$VENV" = "False" ]; then
	EXTRA="--user"
fi

snagboot_version=$(grep "__version__" src/snagrecover/__init__.py | grep -E -o "$PACKAGE_VERSION_PATTERN")

python3 -m pip install $EXTRA build || exit 1

#old binaries in dist can confuse build
rm -f dist/snagboot-*.whl dist/snagboot*.tar.gz
python3 -m build || exit 2

if [ "$1" = "--with-gui" ]; then
	GUI_FEATURE="[gui]"
else
	GUI_FEATURE=""
fi

python3 -m pip install $EXTRA "dist/snagboot-$snagboot_version-py3-none-any.whl$GUI_FEATURE"  --force-reinstall || exit 3

exit 0
