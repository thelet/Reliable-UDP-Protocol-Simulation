import json
import socket
import struct
import time
from typing import Dict, Optional

CLIENT_HEADERS = ["GET_MAX", "MSG", "CLOSE", "DONE"]
SERVER_HEADERS = ["ACK", "DISCONNECT", "RETURN_MAX", "TEMP"]
max_header_size = max( len(s) for s in CLIENT_HEADERS + SERVER_HEADERS)
PACKAGE_COUNT = 0
HEADER_SIZE = 32




class Package:

    def __init__(self, header: str, payload :str = "empty package"):
        global PACKAGE_COUNT
        self.prev_seq = PACKAGE_COUNT
        self.pos = PACKAGE_COUNT
        if header in CLIENT_HEADERS :
            self.seq = PACKAGE_COUNT
            PACKAGE_COUNT += 1
        elif header in SERVER_HEADERS :
            self.seq = 0
        else:
            raise ValueError(f"Invalid header: {header}")
        self.header = header
        self.sent_time = time.time()
        self.payload = str(payload)
        self.ackrecv = False





    # function to print the packet with its variables
    def __str__(self):
        return (
            f"\nsequence:  {self.seq} \ndata: {self.payload} \nsent time: {self.sent_time} \nACK: {self.ackrecv}\n"
            f" prev seq: {self.prev_seq} \n pos: {self.pos} \n")

######################
#   ACKs   #
######################

    def recvack(self):
        self.ackrecv = True


    def send_ack(self, sock: socket, max_payload : int = 10):
        Package.ackrecv = True
        ack_package = Package("ACK", str(self.seq))
        sock.send(ack_package.encode_package(max_payload))
        print(f"ACK{str(self.seq)} sent!")


######################
#   encode\decode   #
######################

    def encode_package(self, max_payload) -> bytes:
        global max_header_size
        """
        Serialize the package into a fixed-size byte structure.

        Format:
        - header: 10 bytes (string, padded with \x00)
        - payload: 50 bytes (string, padded with \x00)
        - seq: 4 bytes (integer)
        - sent_time: 8 bytes (double)
        - ack_state: 1 byte (boolean)
        - prev_seq: 4 bytes (integer)
        - pos : 4 bytes (integer)
        """
        # Pad or truncate the header/payload
        fixed_header = self.header[:max_header_size].ljust(max_header_size, "\x00")
        fixed_payload = self.payload[:max_payload].ljust(max_payload, "\x00")

        # Define the struct format
        # Explanation:
        # - 10s -> 10-byte string
        # - 50s -> 50-byte string
        # - i   -> 4-byte integer
        # - d   -> 8-byte double (floating-point)
        # - ?   -> 1-byte boolean
        # - i   -> 4-byte integer
        #- i   -> 4-byte integer
        format_str = f"{max_header_size}s{max_payload}s i d ? i i"

        # Pack the data
        encoded = struct.pack(
            format_str,
            fixed_header.encode("utf-8"),
            fixed_payload.encode("utf-8"),
            self.seq,
            self.sent_time,
            self.ackrecv,
            self.prev_seq,
            self.pos
        )
        return encoded

    def decode_package(self, package_bytes: bytes, max_payload):
        """
        Deserialize from the fixed-size byte structure back into the Package fields.
        """
        global max_header_size
        # Must match the same format used in encode_package
        format_str = f"{max_header_size}s{max_payload}s i d ? i i"

        #try:
        unpacked_data = struct.unpack(format_str, package_bytes)
        #except struct.error as e:
            #raise ValueError(f"Error unpacking data: {e} + max payload : {max_payload}")

        # Unpacked data returns a tuple in the same order
        raw_header, raw_payload, seq, sent_time, ack_state, prev_seq, pos = unpacked_data

        # Decode strings and strip any trailing nulls
        self.header = raw_header.decode("utf-8").rstrip("\x00")
        self.payload = raw_payload.decode("utf-8").rstrip("\x00")
        self.seq = seq
        self.sent_time = sent_time
        self.ackrecv = ack_state
        self.prev_seq = prev_seq
        self.pos = pos



######################
#   resend updates   #
######################
    def update_for_resend(self, prev_seq, prev_pos):
        global PACKAGE_COUNT
        self.sent_time = time.time()
        self.prev_seq = prev_seq
        self.seq = PACKAGE_COUNT
        self.pos = prev_pos
        PACKAGE_COUNT += 1

    def get_package_for_resend(self,  prev_seq : int, prev_pos : int):
        new_pack = Package(self.header, self.payload)
        new_pack.update_for_resend(prev_seq, prev_pos)
        return new_pack

    def update_time(self):
        self.sent_time = time.time()




######################
#      getters      #
######################

    def getSeq(self):
        return int(self.seq)
    def get_time(self):
        return self.sent_time
    def get_ack_state(self):
        return self.ackrecv
    def get_payload(self):
        return self.payload
    def get_header(self):
        return self.header
    def get_prev_seq(self):
        return self.prev_seq
    def get_pos(self):
        return self.pos


#decode for payload type "param"
    def get_params(self):
        if self.header == "GET_MAX":
            package_params = {}
            # Split the entire payload by '*'
            lines = self.payload.split("*")
            for line in lines:
                # Clean up whitespace
                line = line.strip()
                if not line:
                    continue
                if ":" not in line:
                    print(f"Skipping malformed line: {line}")
                    continue
                # Split once by ':' to separate key from value
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                # Store in our dictionary
                package_params[key] = value
            return package_params
        else:
            print("Invalid package header")
            return None


class AckPackage(Package):
    def __init__(self, recv_package : Package):
        super().__init__("ACK",payload= str(recv_package.getSeq()))
        self.seq = recv_package.getSeq()


class GetPackage(Package):
    def __init__(self, params: Dict[str, str]):
        super().__init__("GET_MAX", "")
        # Build the payload using '*' to separate parameters
        # and ':' to separate key-value within each parameter.        #
        str_params = (
            f"massage:{params['massage']}"      
            f"*maximum_msg_size:{params['maximum_msg_size']}"
            f"*window_size:{params['window_size']}"
            f"*timeout:{params['timeout']}"
        )
        self.payload = str_params



class MsgPackage(Package):
    def __init__(self, payload : str, seq : Optional[int] = None):
        super().__init__(header="MSG",  payload= payload,seq=seq)


class ClosePackage(Package):
    def __init__(self, seq : Optional[int] = None):
        super().__init__("CLOSE", "", seq = seq)

