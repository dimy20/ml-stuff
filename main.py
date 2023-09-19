#! venv/bin/python3
import bencodepy as ben
import sys
import socket
import json

import numpy as np

import struct
import random

from client import Client
import utils

LOCAL_ADDR = "0.0.0.0"
LOCAL_PORT = 2256

def bencode_keys_to_string(data):
    if isinstance(data, dict):
        res = {}
        for key, value in data.items():
            if isinstance(key, bytes):
                new_key = key.decode()

            if isinstance(value, (list, dict)):
                res[new_key] = bencode_keys_to_string(value)
            else:
                res[new_key] = value
        return res
    elif isinstance(data, list):
        return [bencode_keys_to_string(l) for l in data]
    else:
        return data

def load_torrent(fname):
    with open(fname, "rb") as f:
        buf = f.read()
    return bencode_keys_to_string(ben.decode(buf))

def main():
    torrent_data = load_torrent("big-buck-bunny.torrent")
    client = Client(torrent_data)
    if client.run_loop():
        print("Connected to Tracker")

if __name__ == '__main__':
    main()
