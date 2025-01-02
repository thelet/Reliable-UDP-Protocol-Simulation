import socket  #import the socket library, using for sending packets and create a connection
import time  #import the time library to get the time of the packet creation, for timeouts and more
from re import split
from typing import Dict, Optional


class Package:  # class for Packet in Quic Protocol
    sequence = 0  # static vaiable just to keep every new packet uniq ever resended pack helps for the resend algo

    def __init__(self,header : str, payload :str, seq : Optional[int] = None):  # intialize of Quic packet with multiple fields
        # for different packets to have different sequence number according to their order creation
        if seq is None:
            self.seq =0
        else:
            self.seq = seq  # intialize each packet uniq sequence number
        Package.sequence += 1  # static variable to keep track of every packet sequence number and
        self.sent_time = time.time()  # each packet time of creation
        self.payload = payload  # each packet content
        self.header = header
        self.ackrecv = False  # to check if a packet has received in the server

    # function to print the packet with its variables
    def __str__(self):
        return (
            f"\nsequence:  {self.seq} \ndata: {self.payload} \nsent time: {self.sent_time} \nACK: {self.ackrecv}\n ")


    # function to receive each packet sequence number
    def getSeq(self):
        return self.seq

    def get_time(self):
        return self.sent_time

    ##################################################SERVER-FUNCTIONS######################################################

    # function for packets that arrived in the server(ack received)
    def recvack(self):
        self.ackrecv = True

    # function to send and print ack from the server side
    def send_ack(self, sock: socket):
        Package.ackrecv = True
        ack_package = AckPackage(self)
        sock.send(ack_package.encode_package())
        print(f"ACK{str(self.seq)} sent!")

    def get_ack_state(self):
        return self.ackrecv
    #######################################################CLIENT-FUNCTIONS##################################################

    # function that update the creation time and sequence number for a new packet
    def decode_package(self, package_bytes: bytes):
        string_package = package_bytes.decode("utf-8")
        string_package = string_package.split("&")
        print(string_package)
        self.header = string_package[0]
        self.seq = string_package[1]
        self.sent_time = string_package[2]
        self.payload = string_package[3]
        self.ackrecv = False
        Package.sequence -=1

    # funtion that updates a new packet for sending new packet
    # (because of packet loss, we need to send packets again and update their time creation and their sequence number)
    def update_for_resend(self):
        self.sent_time = time.time()

    # encode and send the packet
    def encode_package(self):
        if not self.payload:  # if the packet doesn't have payload we don't need to encode it
            return {}
        encoded = f"{self.header}&{self.seq}&{self.sent_time}&{self.payload}"
        return encoded.encode("utf-8") # send the encoded packet

    def get_payload(self):
        return self.payload
    def get_header(self):
        return self.header

    def get_params(self):
        """
        Parse the payload if header == "GET_MAX" using the convention:
          1) Split the payload by '*'
          2) For each chunk, split by '&' into key and value
        """
        if self.header == "GET_MAX":
            package_params = {}
            # Split the entire payload by '*'
            lines = self.payload.split("*")

            for line in lines:
                # Clean up whitespace
                line = line.strip()
                if not line:
                    # Skip empty or malformed lines
                    continue

                # Each line should be "key&value"
                if ":" not in line:
                    print(f"Skipping malformed line: {line}")
                    continue

                # Split once by '&' to separate key from value
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
        super().__init__("ACK",payload= str(recv_package.getSeq()), seq = recv_package.getSeq())


class GetPackage(Package):
    def __init__(self, params: Dict[str, str]):
        super().__init__("GET_MAX", "")
        # Build the payload using '*' to separate parameters
        # and '&' to separate key-value within each parameter.
        #
        # For example, if params = {
        #     "massage": "ddd",
        #     "maximum_msg_size": "2",
        #     "window_size": "3",
        #     "timeout": "2"
        # }
        # we get:
        # "massage&ddd*maximum_msg_size&2*window_size&3*timeout&2"

        str_params = (
            f"massage:{params['massage']}"        # key=massage & value=ddd
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

