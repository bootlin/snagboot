import yaml
import os
import re

from snagfactory.fastboot import FastbootTask
from snagfactory.utils import SnagFactoryConfigError

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
path_rule = str_rule("[\w\-\/\.]+")

fastboot_cmd_rule = str_rule("\w+(:.+)?")

int_rule = {"type": int}
bool_rule = {"type": bool}

partition_rule = {
	"image": path_rule,
	"image-offset": int_rule,
	"name": str_rule("^[\w][\w\-]*"),
	"start": str_rule("(\-|(\d+M?))"),
	"size": str_rule("(\-|(\d+M?))"),
	"bootable": bool_rule,
	"uuid": str_rule("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
	"type": str_rule("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
}

soc_model_rule = {
"type": dict,

"device-num": int_rule,

"device-type": str_rule("mmc"),

"firmware": {
	"type": dict,
	".+": {
		"type": dict,
		".+": str_rule(".+"),
	},
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

config_rule = {
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
		config = yaml.safe_load(file)

	check_config(config)

	pipelines = {}

	i = 0
	for soc_model,soc_config in config["soc_families"].items():
		pipelines[soc_model] = [FastbootTask(soc_config, i)]
		i += 1

	return config, pipelines

def check_entry(entry, rule):
	entry_type = type(entry)

	if entry_type is dict:
		# check keys
		entry_keys = set(entry.keys())
		rule_keys = set(rule.keys())
		if not entry_keys.issubset(rule_keys):
			# check for regex matches
			suspicious_keys = entry_keys - rule_keys
			matching_keys = set()
			for key in suspicious_keys:
				for rule_key in rule_keys:
					pattern = re.compile(f"^{rule_key}$")
					if pattern.match(key) is not None:
						rule[key] = rule[rule_key]
						matching_keys.add(key)

			if matching_keys != suspicious_keys:
				raise SnagFactoryConfigError(f"Found unknown parameter(s): {suspicious_keys - matching_keys}")

		# check parameter types
		for key,value in entry.items():
			param_type = rule[key]["type"]
			if not isinstance(value, param_type):
				raise SnagFactoryConfigError(f"Parameter {key} has invalid type! {type(value)} instead of {param_type}")

		# check parameter values
		for key,value in entry.items():
			check_entry(value, rule[key])
			param_type = rule[key]["type"]

	elif entry_type is str:
		pattern = re.compile(f"^{rule['pattern']}$")
		match = pattern.match(entry)
		if match is None:
			raise SnagFactoryConfigError(f"Parameter with pattern {pattern.pattern} has invalid value {entry}")

	elif entry_type is list:
		for sub_entry in entry:
			check_entry(sub_entry, rule["rule"])

def check_config(config):
	# Check config syntax
	check_entry(config, config_rule)

	for soc_family in config["soc_families"].values():
		for firmware in soc_family["firmware"].values():
			if not os.path.exists(firmware["path"]):
				raise SnagFactoryConfigError(f"firmware file {firmware['path']} does not exist!")
