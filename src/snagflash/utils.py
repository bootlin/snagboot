
def int_arg(arg: str) -> int:
	if "x" in arg:
		return int(arg, base=16)
	else:
		return int(arg)

