from snagfactory.config import read_config
from snagfactory.gui import SnagFactoryApp
from snagfactory.session import SnagFactorySession
from snagrecover.usb import SnagbootUSBContext

import unittest

print("Testing config file reader")

config_files = ["docs/snagfactory-emmc.yaml", "docs/snagfactory-mtd.yaml"]

for config_file in config_files:
	read_config(config_file, check_paths=False)

print("Testing QML correctness")

app = SnagFactoryApp()

app.shutdown()

print("Testing Snagfactory session init")

session = SnagFactorySession(None)

print("Testing Snagboot USB context initialization")

try:
	SnagbootUSBContext.rescan()
	print("Testing Snagboot USB context hard rescan")
	SnagbootUSBContext.hard_rescan()
except Exception as e:
	# Skip USB tests if no backend is available (e.g., in Windows CI env)
	print(f"Skipping USB tests: {e}")

print("Executing unit tests")
unit_tests = unittest.TestLoader().discover("tests", "*.py")

unit_runner = unittest.TextTestRunner()
unit_result = unit_runner.run(unit_tests)

if not unit_result.wasSuccessful():
	raise RuntimeError(
		f"Unit tests failed, errors: {len(unit_result.errors)} failures: {len(unit_result.failures)}"
	)

print("All tests ran without errors")
