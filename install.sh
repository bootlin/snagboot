#!/bin/env sh

EXTRA=""
if [ -z "${VIRTUAL_ENV_PROMPT}" ]; then
	EXTRA="--user"
fi

python3 -m pip install $EXTRA build || exit 1
python3 -m build || exit 2
python3 -m pip install $EXTRA dist/snagboot-*-py3-none-any.whl  --force-reinstall || exit 3

exit 0
