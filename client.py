import random
from enum import Enum
import socket
import struct
import sys
import json
import utils
import hashlib
import select
from urllib.parse import urlparse

MAGIC = 0x41727101980
CLIENT_NAME = "ET"
CLIENT_VERSION = "0001"
PORT = 6687

class State(int, Enum):
    IDDLE = 0,
    CONNECTED = 0

class Event(int, Enum):
    NONE = 0
    COMPLETED = 1
    STARTED = 2
    STOPPED = 3

class Action(int, Enum):
    CONNECT = 0
    ANNOUNCE = 1

def get_udp_trackers(ben) -> (str, int):
    announce_list = ben["announce-list"]
    res : [(str, int)] = []

    for a in announce_list:
        url = a[0].decode('utf-8')
        tracker = urlparse(url)
        if tracker.scheme == 'udp':
            host = socket.gethostbyname(tracker.hostname)
            res.append((host, int(tracker.port)))

    return res

class Client:
    def __init__(self, bencode):
        self.bencode = bencode
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", PORT))
        self.sock.settimeout(2)

        self.transaction_id = int(random.randrange(0, 255))
        self.connection_id = None
        self.peer_id = f"-{CLIENT_NAME}{CLIENT_VERSION}-".encode("utf-8") + random.randbytes(12)
        self.downloaded = 0
        self.left = self.get_left_bytes()
        self.uploaded = 0
        self.state = State.IDDLE

        self.tracker_adresses = get_udp_trackers(self.bencode)
        self.tracker_addr = (None, None)

    def get_left_bytes(self) -> int:
        if "length" in self.bencode:
            return self.bencode["length"]
        else:
            total = 0
            for file in self.bencode["info"]["files"]:
                total += file["length"]
            return total

    def process_connect_response(self, data : bytes) -> bool:
        if len(data) < 16:
            sys.stderr.write("Bad tracker response\n")
            return False

        res = struct.unpack("!IIQ", data)
        action, transaction_id, connection_id = res

        if self.transaction_id != transaction_id:
            sys.stderr.write("Invalid transaction id received from tracker\n")
            return False

        if action != Action.CONNECT:
            return False

        self.connection_id = connection_id
        return True


    def create_connection_request(self):
        buffer = struct.pack("!q", MAGIC)  # first 8 bytes is connection id
        buffer += struct.pack("!i", Action.CONNECT)  # next 4 bytes is action
        buffer += struct.pack("!i", self.transaction_id)  # next 4 bytes is transaction id
        return buffer, self.transaction_id
    
    def get_info_hash(self) -> bytes:
        info_buf = utils.pack_dict(self.bencode["info"])
        sha1 = hashlib.sha1()
        sha1.update(info_buf)
        return sha1.digest()
        
    def create_announce_msg(self):
        assert self.connection_id != None

        buf = struct.pack(">Q", self.connection_id) # connection id
        buf += struct.pack(">I", Action.ANNOUNCE) # action
        buf += struct.pack(">I", self.transaction_id) #transaction id
        buf += self.get_info_hash() # info hash
        buf += self.peer_id # peer id
        buf += struct.pack(">Q", self.downloaded) # downloaded bytes
        buf += struct.pack(">Q", self.left) # left bytes
        buf += struct.pack(">Q", self.uploaded) # uploaded bytes
        buf += struct.pack(">I", Event.STARTED) # event
        buf += struct.pack(">I", 0) # ip address 0 default
        buf += struct.pack(">I", random.randint(0, 255)) # random key?
        buf += struct.pack(">i", -1) # num want
        buf += struct.pack(">H", PORT)

        return buf

    def send_announce_msg(self):
        assert self.state == State.CONNECTED

        announce_msg = self.create_announce_msg()
        try:
            print(f"Sending announce to tracker: {self.tracker_addr}")
            self.sock.sendto(announce_msg, self.tracker_addr)
            return True
        except socket.error as e:
            sys.stderr.write(f"Error: {e.strerror}\n")
            return False


    def try_trackers(self) -> bool:
        assert self.state == State.IDDLE

        req_msg_buf, _= self.create_connection_request()
        for tracker_addr in self.tracker_adresses:
            self.sock.sendto(req_msg_buf, tracker_addr)
            try:
                data, addr = self.sock.recvfrom(1024)
                if self.process_connect_response(data):
                    self.state = State.CONNECTED
                    self.tracker_addr = tracker_addr

                    if not self.send_announce_msg():
                        return False

                    return True

            except socket.timeout as e:
                sys.stderr.write(f"Error: connection to {tracker_addr} {e}\n")

        return False

    def process_read_event(self):
        data, addr = self.sock.recvfrom(1024)

        if addr == self.tracker_addr:
            print(f"Received {len(data)} bytes from tracker {self.tracker_addr}")


    def run_loop(self) -> bool:
        if not self.try_trackers():
            return False
        assert self.state == State.CONNECTED
        print(f"Connected to tracker: {self.tracker_addr}")

        self.sock.setblocking(0)
        intrested = [self.sock]

        while True:
            read_events, _, _= select.select(intrested, [], [])

            for sock in read_events:
                if sock == self.sock:
                    self.process_read_event()
