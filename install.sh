#!/bin/env sh

if [ -z "${VIRTUAL_ENV_PROMPT}" ]; then
    python3 -m pip install --user build || exit 1
else
    python3 -m pip install build || exit 1
fi

python3 -m build || exit 2
python3 -m pip install dist/snagboot-*-py3-none-any.whl  --force-reinstall || exit 3

exit 0
