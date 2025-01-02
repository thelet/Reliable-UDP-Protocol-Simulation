import socket
import sys
import time
from socket import AF_INET, SOCK_STREAM
from threading import Thread, main_thread
from typing import Dict

from package import Package, AckPackage, GetPackage, MsgPackage,ClosePackage


########################################
# הגדרה גלובלית של המשתנים
########################################

HOST = '127.0.0.1'
PORT = 33002
BUFSIZ = 1024
ADDR = (HOST, PORT)
PARAMS = {}
CURRENT_PACKAGES = {}
LAST_ACK_SEQ : int = 0
LAST_ACK_TIME =None
PACKAGE_COUNT =0

########################################
# פתיחה של ה SOCKET וחיבור לשרת
########################################
def create_client_socket():
    client_socket = socket.socket(AF_INET, SOCK_STREAM)
    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    client_socket.connect(ADDR)
    initial_connection(client_socket)
    return client_socket

def initial_connection(client_socket):
    client_socket.send(Package("GET_MAX", " ").encode_package())


def receive(client_socket):
    """Continuously listens for messages (or ACKs) from the server."""
    global PARAMS
    global LAST_ACK_SEQ
    global LAST_ACK_TIME
    while True:
        try:
            data = client_socket.recv(BUFSIZ)
            new_package = Package(" ", " ")
            new_package.decode_package(data)

            header = new_package.get_header()

            if header == "GET_MAX":
                GET_MAX_Header(params_package= new_package)

            elif header == "ACK":
                ACK_Header(ack_package= new_package)

            elif header == "CLOSE":
                CLOSE_Header(client_socket= client_socket)

            elif not data:
                CLOSE_Header(client_socket= client_socket)
                break

            else:
                print(f"Undetected header: \nRaw data received : {data}", flush=True)

        except OSError as e:
            # Check if the error is specifically WinError 10054
            if hasattr(e, 'winerror') and e.winerror == 10054:
                print(f"Server forcibly closed the connection", flush=True)
            else:
                print(f"Error while receiving data: {e}", flush=True)
            CLOSE_Header(client_socket=client_socket)
            break


def send_data(package : Package, client_socket):
    global CURRENT_PACKAGES
    try:
        print(f"SENDING package :\n {CURRENT_PACKAGES.get(seq)}" for seq in CURRENT_PACKAGES)
        client_socket.send(package.encode_package())
        CURRENT_PACKAGES.update({package.getSeq(): package})
    except Exception as e:
        print(f"Error while sending data: {e} package seq {package.getSeq()}")


def handle_lost_packages(client_socket):
    global CURRENT_PACKAGES
    for seq in CURRENT_PACKAGES:
        package = CURRENT_PACKAGES.get(seq)
        if not package.get_ack_state() and check_treshhold(package):
            print(f"RESEND:\n{package}\n")
            send_data(package, client_socket)



def slice_data(data : bytes):
    chunks = []
    for i in range(0, len(data), int(PARAMS["maximum_msg_size"])):
        chunks.append(data[i:i + int(PARAMS["maximum_msg_size"])])
    return chunks


def create_msg_packages_list(slice_list : list[bytes]):
    global PACKAGE_COUNT
    packages_to_send = []
    for data_slice in slice_list:
        package = MsgPackage(data_slice.decode("utf-8"), seq= PACKAGE_COUNT)
        PACKAGE_COUNT += 1
        packages_to_send.append(package)
    finish_package = Package("DONE", "EOMsg", seq= PACKAGE_COUNT)
    PACKAGE_COUNT += 1
    packages_to_send.append(finish_package)
    for package in packages_to_send:
        print(f"CREATED package type: {package.get_header()} seq: {package.getSeq()} with DATA: {package.get_payload()}")
    return packages_to_send


def check_treshhold(package : Package):
    global LAST_ACK_TIME
    global LAST_ACK_SEQ
    if int(package.getSeq() - int(LAST_ACK_SEQ) > int(PARAMS["window_size"])):
        print(f"window size threshold passed: \nlast ack number: {LAST_ACK_SEQ} current pack number: {package.getSeq()} diff: {int(package.getSeq()) - int(LAST_ACK_SEQ)} ")
        return False
    elif not LAST_ACK_TIME is None:
        if LAST_ACK_TIME - package.get_time() > int(PARAMS["timeout"]):
            print(f"time threshold passed: \nlast ack time: {LAST_ACK_TIME} current pack time: {package.get_time()} diff: {int(package.get_time()) - int(LAST_ACK_TIME)} )")
            return False
    else:
        return True


def GET_MAX_Header(params_package : Package):
    PARAMS.update(params_package.get_params())
    print(PARAMS)


def ACK_Header(ack_package : Package):
    global LAST_ACK_SEQ
    global LAST_ACK_TIME
    print(f"received ACK {ack_package.payload}")
    acked_pack = CURRENT_PACKAGES.get(int(ack_package.payload))
    if acked_pack is not None:
        acked_pack.recvack()
        LAST_ACK_SEQ = ack_package.payload
        LAST_ACK_TIME = time.time()
    else:
        print(f"Warning: No package found for key '{ack_package.payload}'.")


def CLOSE_Header(client_socket : socket.socket):
    print(fr"Closing connection...")
    client_socket.close()
    sys.exit(0)


def send_CLOSE_msg(client_socket : socket.socket):
    before_closing(client_socket)
    close_package = ClosePackage()
    send_data(close_package, client_socket)


def send_msg_logic(client_socket : socket.socket):
    while True:
        msg = input("\nenter your message: \n")
        sliced_msg = slice_data(msg.encode("utf-8"))
        packages_to_send = create_msg_packages_list(slice_list=sliced_msg)
        for pack in packages_to_send:
            if not check_treshhold(pack):
                print(f"Warning: treshhold for package found. \npackage:{pack} \n Last ack time: {LAST_ACK_TIME} \n Last ack sequence: {LAST_ACK_SEQ}")
                handle_lost_packages(client_socket)

            print(f"TRANSFER for send- package type: {pack.get_header()} seq: {pack.getSeq()} with DATA: {pack.get_payload()}")
            send_data(pack, client_socket)
        if (msg == "-1"):
            send_CLOSE_msg(client_socket = client_socket)
            break
    for package in CURRENT_PACKAGES:
        print(CURRENT_PACKAGES[package])


def all_acks_received():
    return all(CURRENT_PACKAGES.get(seq).get_ack_state() for seq in CURRENT_PACKAGES)


def before_closing(client_socket : socket.socket):
    while not all_acks_received():
        time.sleep(0.5)
        try:
            handle_lost_packages(client_socket)
        except OSError as e:
            print(f"Error while sending last data, closing connection : {e}", flush=True)
            break


def main_client():
    client_socket = create_client_socket()

    # Start a thread to handle receiving messages
    Thread(target=receive, args=(client_socket,)).start()
    if PARAMS is not None:
        send_msg_logic(client_socket)

    client_socket.close()

if __name__ == '__main__':
    main_client()
