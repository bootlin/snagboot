#!/bin/bash
python3 -m pip install build
python3 -m build
python3 -m pip install --user dist/snagboot-*-py3-none-any.whl  --force-reinstall
