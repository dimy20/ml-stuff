#! venv/bin/python3
import bencodepy as ben
from dataclasses import dataclass
import socket
import sys
from urllib.parse import urlparse
from enum import Enum

import struct
import random

LOCAL_ADDR = "0.0.0.0"
LOCAL_PORT = 2256
MAGIC = 0x41727101980  # default connection id

class Action(int, Enum):
    CONNECT = 0

def load_torrent(fname):
    with open(fname, "rb") as f:
        buf = f.read()
    return buf

def create_connection_request():
    transaction_id = int(random.randrange(0, 255))
    buffer = struct.pack("!q", MAGIC)  # first 8 bytes is connection id
    buffer += struct.pack("!i", Action.CONNECT)  # next 4 bytes is action
    buffer += struct.pack("!i", transaction_id)  # next 4 bytes is transaction id
    return buffer, transaction_id

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
    torrent_data = load_torrent("big-buck-bunny.torrent")
    b = ben.decode(torrent_data)
    tracker_adresses = get_udp_trackers(b)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)
    req_msg_buf, _= create_connection_request()

    for tracker_addr in tracker_adresses:
        sock.sendto(req_msg_buf, tracker_addr)
        try:
            data, addr = sock.recvfrom(1024)
            print(f"got : {len(data)} bytes from tracker")
            print(f"Connection to : {tracker_addr} succeeded")
        except socket.timeout:
            print(f"Connection to : {tracker_addr} failed")


if __name__ == '__main__':
    main()
