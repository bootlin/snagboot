from snagfactory.config import read_config
from snagfactory.gui import SnagFactory
from snagfactory.session import SnagFactorySession
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

print("All tests ran without errors")
