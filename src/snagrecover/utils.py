import os
import sys

def access_error(dev_type: str, dev_addr: str):
	print(f"Device access error: failed to access {dev_type} device {dev_addr}, please check its presence and access rights", file=sys.stderr)
	sys.exit(-1)

def cli_error(error: str):
	print(f"CLI error: {error}", file=sys.stderr)
	sys.exit(-1)

def dnload_iter(blob: bytes, chunk_size: int):
	#parse binary blob by chunks of chunk_size bytes
	L = len(blob)
	N = L // chunk_size
	R = L % chunk_size
	for i in range(N):
		yield blob[chunk_size * i:chunk_size * (i + 1)]
	if R > 0:
		yield blob[chunk_size * N:chunk_size * N + R]

