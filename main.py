#! venv/bin/python3
import bencodepy as ben
import sys
from urllib.parse import urlparse
import socket

import numpy as np

import struct
import random

from client import Client

LOCAL_ADDR = "0.0.0.0"
LOCAL_PORT = 2256

def load_torrent(fname):
    with open(fname, "rb") as f:
        buf = f.read()
    return buf

def get_udp_trackers(ben) -> (str, int):
    announce_list = ben[b'announce-list']
    res : [(str, int)] = []

    for a in announce_list:
        url = a[0].decode('utf-8')
        tracker = urlparse(url)
        if tracker.scheme == 'udp':
            host = socket.gethostbyname(tracker.hostname)
            res.append((host, int(tracker.port)))

    return res



def main():
    client = Client()
    torrent_data = load_torrent("big-buck-bunny.torrent")
    b = ben.decode(torrent_data)
    tracker_adresses = get_udp_trackers(b)
    client.announce(tracker_adresses)



if __name__ == '__main__':
    main()
