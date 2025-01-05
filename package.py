import socket
import time
from typing import Dict, Optional


class Package:
    def __init__(self, header : str, payload :str, seq : Optional[int] = None):
        if seq is None:
            self.seq =0
            self.prev_seq = 0
        else:
            self.seq = seq
            self.prev_seq = seq
        self.sent_time = time.time()
        self.payload = payload
        self.header = header
        self.ackrecv = False


    # function to print the packet with its variables
    def __str__(self):
        return (
            f"\nsequence:  {self.seq} \ndata: {self.payload} \nsent time: {self.sent_time} \nACK: {self.ackrecv}\n ")

######################
#   ACKs   #
######################

    def recvack(self):
        self.ackrecv = True


    def send_ack(self, sock: socket):
        Package.ackrecv = True
        ack_package = AckPackage(self)
        sock.send(ack_package.encode_package())
        print(f"ACK{str(self.seq)} sent!")


######################
#   encode\decode   #
######################

    def decode_package(self, package_bytes: bytes):
        string_package = package_bytes.decode("utf-8")
        string_package = string_package.split("&")
        print(string_package)
        self.header = string_package[0]
        self.seq = string_package[1]
        self.sent_time = string_package[2]
        self.payload = string_package[3]
        self.prev_seq = string_package[4]
        self.ackrecv = False


    def encode_package(self):
        if not self.payload:
            return {}
        encoded = f"{self.header}&{self.seq}&{self.sent_time}&{self.payload}&{self.prev_seq}"
        return encoded.encode("utf-8")


######################
#   resend updates   #
######################

    def update_for_resend(self, new_seq , prev_seq):
        self.sent_time = time.time()
        self.prev_seq = prev_seq
        self.seq = new_seq


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
    def __init__(self):
        super().__init__("CLOSE", "")

