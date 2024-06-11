import yaml
import os

def read_config(path):
	with open(path, "r") as file:
		batch = yaml.safe_load(file)

	check_config(batch)

	return batch

def check_config(batch):
	for soc_family in batch["soc_families"].values():
		for firmware in soc_family["firmware"].values():
			if not os.path.exists(firmware["path"]):
				pass

