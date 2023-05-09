import os
import sys

def dnload_iter(blob: bytes, chunk_size: int):
	#parse binary blob by chunks of chunk_size bytes
	L = len(blob)
	N = L // chunk_size
	R = L % chunk_size
	for i in range(N):
		yield blob[chunk_size * i:chunk_size * (i + 1)]
	if R > 0:
		yield blob[chunk_size * N:chunk_size * N + R]

