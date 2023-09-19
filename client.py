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
    CONNECTED = 1
    WAITING_ANNOUNCE_RESPONSE = 2
    # We consider this client to be connected when:
    # (1) => We dont care about the best tracker (Larget swarm) and we have received a sucessfull connect response from any tracker.
    #        Tipically this would be the first one to respond back or the only available tracker if announce-list has only one element.
    # (2) => We care about the best tracker (Largest swarm) and announce-list length is greater than one.
    #        In that case the client state is set to BEST_TRACKER_DISCOVERY, and the state will be changed to CONNECTED once we have found the best tracker.
    # Criteria for best tracker:
    # Currently the client will care only about the number of seeders and leechers to make this decision
    # Makes sense?
    BEST_TRACKER_DISCOVERY = 3

class Event(int, Enum):
    NONE = 0
    COMPLETED = 1
    STARTED = 2
    STOPPED = 3

class Action(int, Enum):
    CONNECT = 0
    ANNOUNCE = 1

class Config():
    def __init__(self, best_tracker = False):
        self.best_tracker = best_tracker

    @staticmethod
    def default() -> 'Config':
        c = Config()
        return c

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

def LOG_ERR(msg: str):
    sys.stderr.write(f"Error: {msg}\n")

class Client:
    def __init__(self, bencode, config : Config = Config.default()):
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
        self.config = config

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
        #print(self.state)
        assert self.state == State.CONNECTED

        announce_msg = self.create_announce_msg()
        try:
            print(f"Sending announce to tracker: {self.tracker_addr}")
            self.sock.sendto(announce_msg, self.tracker_addr)
            self.state = State.WAITING_ANNOUNCE_RESPONSE
            return True
        except socket.error as e:
            sys.stderr.write(f"Error: {e.strerror}\n")
            return False

    # Connects to the first tracker that gives a reponse back.
    def try_one_tracker(self) -> bool:
        assert self.state == State.IDDLE
        req_msg_buf, _= self.create_connection_request()
        for tracker_addr in self.tracker_adresses:
            self.sock.sendto(req_msg_buf, tracker_addr)
            try:
                data, addr = self.sock.recvfrom(1024)
                if self.process_connect_response(data):
                    #This tracker responded sucessfully, we are connected now
                    self.state = State.CONNECTED
                    self.tracker_addr = tracker_addr
                    return True

            except socket.timeout as e:
                sys.stderr.write(f"Error: connection to {tracker_addr} {e}\n")

        return False

    def process_announce_response(self, data, addr) -> bool:
        if len(data) < 20:
            LOG_ERR("Announce response with unsufficient bytes")
            return False

        fields = struct.unpack(">IIIII", data[:20])
        action, transaction_id, interval, leechers, seeders = fields

        if transaction_id != self.transaction_id:
            LOG_ERR(f"Invalid transaction id received from tracker {self.tracker_addr}")
            return False

        if action != Action.ANNOUNCE:
            LOG_ERR(f"Invalid action received from tracker {self.tracker_addr}")
            return False

        print(f"Seeders: {seeders}")
        print(f"Leechers: {leechers}")
        return True

    def try_best_tracker(self):
        assert self.state == State.IDDLE
        self.state = State.BEST_TRACKER_DISCOVERY
        req_msg_buf, _= self.create_connection_request()
        for tracker_addr in self.tracker_adresses:
            self.sock.sendto(req_msg_buf, tracker_addr)
            try:
                data, addr = self.sock.recvfrom(1024)
                if self.process_connect_response(data):
                    #This tracker responded sucessfully, we are connected now
                    self.state = State.CONNECTED
                    self.tracker_addr = tracker_addr
                    #self.candidates += 0

            except socket.timeout as e:
                sys.stderr.write(f"Error: connection to {tracker_addr} {e}\n")

        return False

    def process_read_event(self) -> bool:
        data, addr = self.sock.recvfrom(1024)
        print(len(data))
        if self.state == State.WAITING_ANNOUNCE_RESPONSE:
            if not self.process_announce_response(data, addr):
                return False

    def run_loop(self) -> bool:
        if not self.config.best_tracker:
            if not self.try_one_tracker():
                return False

            assert self.state == State.CONNECTED
            print(f"Connected to tracker: {self.tracker_addr}")

            if not self.send_announce_msg():
                return False
        else:
            sys.stderr.write(f"TODO: implement best tracker discovery\n")
            sys.exit(1)

        self.sock.setblocking(0)
        intrested = [self.sock]

        while True:
            read_events, _, _= select.select(intrested, [], [])

            for sock in read_events:
                if sock == self.sock:
                    self.process_read_event()
