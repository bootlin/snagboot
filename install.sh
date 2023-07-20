#!/bin/env sh

VENV=$(python3 -c "import sys;print(sys.prefix != sys.base_prefix)")
EXTRA=""
if [ "$VENV" = "False" ]; then
	EXTRA="--user"
fi

python3 -m pip install $EXTRA build || exit 1

#old binaries in dist can confuse build
rm -f dist/snagboot-*.whl dist/snagboot*.tar.gz
python3 -m build || exit 2

python3 -m pip install $EXTRA dist/snagboot-*-py3-none-any.whl  --force-reinstall || exit 3

exit 0
