import yaml
import os
import re

class SnagFactoryConfigError(Exception):
	pass

def list_soc_models():
	with open(os.path.dirname(__file__) + "/../snagrecover/supported_socs.yaml", "r") as file:
		socs = yaml.safe_load(file)

	return list(socs["tested"].keys()) + list(socs["untested"].keys())

soc_model_pattern = "(" + "|".join(list_soc_models()) + ")"

def str_rule(pattern: str):
	return {
		"type": str,
		"pattern": pattern,
	}

name_rule = str_rule("[\w\-]+")
path_rule = str_rule("[\w\-\/\\]+")

fastboot_cmd_rule = str_rule("\w+(:.+)?")

int_rule = {"type": int}

partition_rule = {
	"image": path_rule,
	"image-offset": int_rule,
	"name": str_rule("^[\w][\w\-]*"),
	"start": str_rule("(\-|(\d+M?))"),
	"size": str_rule("(\-|(\d+M?))"),
	"bootable": str_rule("[tT]rue"),
	"uuid": str_rule("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
	"type": str_rule("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
}

soc_model_rule = {
"type": dict,

"device-num": int_rule,

"device-type": str_rule("mmc"),

"firmware": {
	"type": dict,
	".+": str_rule(".+"),
},

"partitions": {
	"type": list,
	"rule": partition_rule,
},

"boot0": {
	"type": dict,
	"name": name_rule,
	"image": path_rule,
	"image-offset": int_rule,
},

"boot1": {
	"type": dict,
	"name": name_rule,
	"image": path_rule,
	"image-offset": int_rule,
},

"fb_buffer_size": int_rule,

"post-flash": {
	"type": list,
	"rule": fastboot_cmd_rule,
},

"image": path_rule,

"image-offset": int_rule,
}

config_rules = {
	"type": dict,

	"boards": {
		"type": dict,
		"[\da-fA-F]{4}:[\da-fA-F]{4}": str_rule(soc_model_pattern),
	},

	"soc_families": {
		"type": dict,
		soc_model_pattern: soc_model_rule,
	},
}

def read_config(path):
	with open(path, "r") as file:
		batch = yaml.safe_load(file)

	check_config(batch)

	return batch

def check_entry(entry: dict, rules):
	# check keys
	entry_keys = set(entry.keys())
	rules_keys = set(rules.keys())
	if not entry_keys.issubset(rules_keys):
		# check for regex matches
		suspicious_keys = entry_keys - rules_keys
		matching_keys = set()
		for key in suspicious_keys:
			for rules_key in rules_keys:
				pattern = re.compile(f"^{rules_key}$")
				if pattern.match(key) is not None:
					rules[key] = rules[rules_key]
					matching_keys.add(key)

		if matching_keys != suspicious_keys:
			raise SnagFactoryConfigError(f"Found unknown parameter(s): {suspicious_keys - matching_keys}")

	# check parameter types
	for key,value in entry.items():
		entry_type = rules[key]["type"]
		if not isinstance(value, entry_type):
			raise SnagFactoryConfigError(f"Parameter {key} has invalid type! {type(value)} instead of {entry_type}")

	# check parameter values
	for key,value in entry.items():
		entry_type = rules[key]["type"]

		if entry_type is str:
			pattern = re.compile(f"^{rules[key]['pattern']}$")
			match = pattern.match(value)
			if match is None:
				raise SnagFactoryConfigError(f"Parameter {key} with pattern {pattern.pattern} has invalid value {value}", {"entry": entry, "rules": rules})
		elif entry_type is list:
			for sub_entry in value:
				check_entry(sub_entry, rules[key]["rule"])
		elif entry_type is int:
			return
		else:
			check_entry(value, rules[key])

def check_config(batch):
	# Check config syntax
	check_entry(batch, config_rules)

	for soc_family in batch["soc_families"].values():
		for firmware in soc_family["firmware"].values():
			if not os.path.exists(firmware["path"]):
				raise SnagFactoryConfigError(f"firmware file {firmware['path']} does not exist!")
