import yaml
import os
import re

from snagrecover.utils import get_supported_socs, get_soc_aliases

from snagfactory.fastboot import task_table
from snagfactory.utils import SnagFactoryConfigError

any_rule = {
	"type": object,
}


def list_soc_models():
	socs = get_supported_socs()
	aliases = get_soc_aliases(socs)

	return (
		list(socs["tested"].keys())
		+ list(socs["untested"].keys())
		+ list(aliases.keys())
	)


soc_model_pattern = "(" + "|".join(list_soc_models()) + ")"


def str_rule(pattern: str):
	return {
		"type": str,
		"pattern": pattern,
	}


name_rule = str_rule(r"[\w\-]+")
path_rule = str_rule(r"[\w\-\/\.:]+")

fastboot_cmd_rule = str_rule(r"\w+(:.+)?")

int_rule = {"type": int}
bool_rule = {"type": bool}

euda_rule = {
	"type": dict,
	"start": int_rule,
	"size": int_rule,
	"wrrel": bool_rule,
}

gp_rule = {
	"type": dict,
	"size": int_rule,
	"enh": bool_rule,
	"wrrel": bool_rule,
}

emmc_hwpart_task_rule = {
	"type": dict,
	"task": str_rule(r"emmc-hwpart"),
	"args": {
		"type": dict,
		"euda": euda_rule,
		r"gp\d": gp_rule,
		"skip-pwr-cycle": bool_rule,
	},
}

prompt_operator_task_rule = {
	"type": dict,
	"task": str_rule(r"prompt-operator"),
	"args": {
		"type": dict,
		"prompt": str_rule(r".+"),
		"reset-before": bool_rule,
	},
}

reset_task_rule = {
	"type": dict,
	"task": str_rule(r"reset"),
}

flash_rule = {
	"type": dict,
	"part": str_rule(r"([\w\-\.]+|hwpart \d)"),
	"image": path_rule,
	"image-offset": int_rule,
}

flash_task_rule = {
	"type": dict,
	"task": str_rule(r"flash"),
	"args": {
		"type": list,
		"rules": [
			flash_rule,
		],
	},
}

mtd_part_rule = {
	"type": dict,
	"image": path_rule,
	"image-offset": int_rule,
	"name": str_rule(r"[\w][\w\-\.]*"),
	"start": int_rule,
	"size": int_rule,
	"ro": bool_rule,
}

partition_rule = {
	"type": dict,
	"image": path_rule,
	"image-offset": int_rule,
	"name": str_rule(r"[\w][\w\-]*"),
	"start": int_rule,
	"size": int_rule,
	"bootable": bool_rule,
	"uuid": str_rule(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
	"type()": str_rule(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
}

run_task_rule = {
	"type": dict,
	"task": str_rule(r"run"),
	"args": {
		"type": list,
		"rules": [
			fastboot_cmd_rule,
		],
	},
}

mtd_parts_task_rule = {
	"type": dict,
	"task": str_rule(r"mtd-parts"),
	"args": {
		"type": list,
		"rules": [
			mtd_part_rule,
		],
	},
}

gpt_task_rule = {
	"type": dict,
	"task": str_rule(r"gpt"),
	"args": {
		"type": list,
		"rules": [
			partition_rule,
		],
	},
}

globals_rule = {
	"type": dict,
	"target-device": str_rule(r"[\w\-]+"),
	"fb-buffer-size": int_rule,
	"fb-buffer-addr": int_rule,
	"eraseblk-size": int_rule,
}

tasks_rule = {
	"type": list,
	"rules": [
		globals_rule,
		gpt_task_rule,
		mtd_parts_task_rule,
		run_task_rule,
		flash_task_rule,
		reset_task_rule,
		prompt_operator_task_rule,
		emmc_hwpart_task_rule,
	],
}

config_rule = {
	"type": dict,
	"boards": {
		"type": dict,
		r"[\da-fA-F]{4}:[\da-fA-F]{4}": str_rule(soc_model_pattern),
	},
	"soc-models": {
		"type": dict,
		f"{soc_model_pattern}-firmware": {
			"type": dict,
			".+": any_rule,
		},
		f"{soc_model_pattern}-tasks": tasks_rule,
	},
}


def map_config(config, modify):
	if isinstance(config, dict):
		key_list = list(config.keys())
		for key in key_list:
			value = config[key]

			if isinstance(value, dict) or isinstance(value, list):
				map_config(value, modify)
			else:
				config[key] = modify(value)

	elif isinstance(config, list):
		for i in range(len(config)):
			value = config[i]

			if isinstance(value, dict) or isinstance(value, list):
				map_config(value, modify)
			else:
				config[i] = modify(value)


def suffixed_num_to_int(param) -> int:
	pattern = re.compile(r"^\d+[GMKgmk]?$")

	if not isinstance(param, str) or pattern.match(param) is None:
		return param

	suffix = param[-1]
	num = param[:-1]

	if suffix in ["k", "K"]:
		multiplier = 1024
	elif suffix in ["m", "M"]:
		multiplier = 1024**2
	elif suffix in ["g", "G"]:
		multiplier = 1024**3
	else:
		raise SnagFactoryConfigError(f"Invalid suffix {suffix}")

	return int(num) * multiplier


def preprocess_config(config):
	"""
	This performs the following transformations on the parsed YAML config file:
	- find strings of the form "[0-9]+(M|k)?" and convert them to integers
	"""

	map_config(config, suffixed_num_to_int)


def read_config(path, check_paths=True):
	with open(path, "r") as file:
		config = yaml.safe_load(file)

	preprocess_config(config)

	check_config(config, check_paths)

	pipelines = {}
	for soc_key, soc_config in config["soc-models"].items():
		soc_model, sep, suffix = soc_key.partition("-")

		if suffix == "firmware":
			continue

		# First entry must be global vars
		globals = soc_config[0]
		pipelines[soc_model] = []

		i = 0
		for entry in soc_config[1:]:
			if "task" not in entry:
				# Treat all non-task entries as global variable updates
				globals.update(entry)
				continue
			elif (task_object := task_table.get(entry["task"], None)) is None:
				raise SnagFactoryConfigError(
					f"Invalid entry {entry}: unknown task {entry['task']}"
				)

			task = task_object(entry.get("args", None), i, globals)
			task.get_cmds()
			pipelines[soc_model].append(task)
			i += 1

	return config, pipelines


def check_entry(entry, rule):
	if rule["type"] is object:
		return

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
				raise SnagFactoryConfigError(
					f"Found unknown parameter(s): {suspicious_keys - matching_keys}"
				)

		# check parameter types
		for key, value in entry.items():
			param_type = rule[key]["type"]
			if param_type is object:
				continue

			if not isinstance(value, param_type):
				raise SnagFactoryConfigError(
					f"Parameter {key} has invalid type! {type(value)} instead of {param_type}"
				)

		# check parameter values
		for key, value in entry.items():
			check_entry(value, rule[key])
			param_type = rule[key]["type"]

	elif entry_type is str:
		pattern = re.compile(f"^{rule['pattern']}$")
		match = pattern.match(entry)
		if match is None:
			raise SnagFactoryConfigError(
				f"Parameter with pattern {pattern.pattern} has invalid value {entry}"
			)

	elif entry_type is list:
		for sub_entry in entry:
			matched = False
			error_msgs = []
			for entry_rule in rule["rules"]:
				try:
					check_entry(sub_entry, entry_rule)
					matched = True
				except SnagFactoryConfigError as e:
					error_msgs.append(e)

			if not matched:
				raise SnagFactoryConfigError(
					f"Invalid list item {sub_entry}, all possible matches failed: {error_msgs}"
				)


def check_config(config, check_paths=True):
	# Check config syntax
	check_entry(config, config_rule)

	soc_models = set(config["boards"].values())
	for soc_model in soc_models:
		# check that each soc has a task section and a firmware section
		if f"{soc_model}-firmware" not in config["soc-models"]:
			raise SnagFactoryConfigError(f"Section {soc_model}-firmware is missing!")

		if f"{soc_model}-tasks" not in config["soc-models"]:
			raise SnagFactoryConfigError(f"Section {soc_model}-tasks is missing!")

		if not check_paths:
			continue

		# check that specified firmware files exist

		for firmware in config["soc-models"][f"{soc_model}-firmware"].values():
			if not os.path.exists(firmware["path"]):
				raise SnagFactoryConfigError(
					f"firmware file {firmware['path']} does not exist!"
				)
