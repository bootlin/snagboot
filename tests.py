from snagfactory.config import read_config
from snagfactory.gui import SnagFactory
from snagfactory.session import SnagFactorySession
from snagrecover.usb import SnagbootUSBContext
from kivy.lang import Builder

print("Testing config file reader")

config_files = ["docs/snagfactory-emmc.yaml", "docs/snagfactory-mtd.yaml"]

for config_file in config_files:
	read_config(config_file, check_paths=False)

print("Testing Kivy application builder")

app = SnagFactory()

Builder.load_file("src/snagfactory/gui.kv")
Builder.load_file("src/snagfactory/config.kv")

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

print("All tests ran without errors")
