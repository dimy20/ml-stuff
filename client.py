import random
from enum import Enum
import socket
import struct
import sys

MAGIC = 0x41727101980
class Action(int, Enum):
    CONNECT = 0

class Client:
    def __init__(self):
        self.transaction_id = int(random.randrange(0, 255))
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(2)
        self.connection_id = None

    def process_connect_response(self, data : bytes) -> bool:
        if len(data) < 16:
            sys.stderr.write("Bad tracker response")
            return False

        res = struct.unpack("!IIQ", data)
        action, transaction_id, connection_id = res

        if self.transaction_id != transaction_id:
            sys.stderr.write("Invalid transaction id received from tracker")
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
    
    def create_announce_msg(self):
        pass

    def announce(self, tracker_adresses):
        req_msg_buf, _= self.create_connection_request()

        for tracker_addr in tracker_adresses:
            self.sock.sendto(req_msg_buf, tracker_addr)
            try:
                data, addr = self.sock.recvfrom(1024)
                if self.process_connect_response(data):
                    print("Connected to tracker")
                break
            except socket.timeout:
                print(f"Connection to : {tracker_addr} failed")


