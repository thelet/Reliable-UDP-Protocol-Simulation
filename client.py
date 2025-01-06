import json
import socket
import sys
import time
from socket import AF_INET, SOCK_STREAM
from threading import Thread, main_thread
from time import sleep
from typing import Dict, List

import select

import package


import functions
from package import Package, AckPackage, GetPackage, MsgPackage,ClosePackage


########################################
# הגדרה גלובלית של המשתנים
########################################

HOST = '127.0.0.1'
PORT = 55558
BUFSIZ = 44
ADDR = (HOST, PORT)
PARAMS : Dict[str,str] ={}
PACKAGES_TO_LOSE = [4,9,10]

CURRENT_PACKAGES : Dict[int,Package]= {}
LAST_ACK_SEQ : int = 1

TIME_WINDOW =0
SEQ_WINDOW = 0



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
    client_socket.send(Package("GET_MAX", "asking for max msg size").encode_package(10))


def receive(client_socket):
    """Continuously listens for messages (or ACKs) from the server."""
    global PARAMS
    while True:
        try:
            data = client_socket.recv(BUFSIZ)
            new_package = Package("TEMP", " ")
            new_package.decode_package(data, 10)

            header = new_package.get_header()

            if header == "RETURN_MAX":
                GET_MAX_Header(params_package= new_package)

            elif header == "ACK":
                ACK_Header(ack_package= new_package)

            elif header == "DISCONNECT":
                print(f"received DISCONNECT msg from server: {new_package} \n")
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



def check_treshhold(package_seq):
    return  check_time_threshold() and check_seq_threshold(package_seq)

def check_time_threshold():
    if package is not None:
        if TIME_WINDOW and TIME_WINDOW <= time.time():
            print(f"time threshold passed: \ncurrent time: {time.time()} current window: {TIME_WINDOW})")
            return False
        else:
            return True

def check_seq_threshold(package_seq):
    global LAST_ACK_SEQ
    if package is not None:
        if SEQ_WINDOW and int(SEQ_WINDOW) < int(package_seq):
            print(
                f"window size threshold passed: \nwindow size: {SEQ_WINDOW} current pack number: {package_seq} diff: {int(package_seq) - int(LAST_ACK_SEQ)} ")
            return False
        else:
            return True


def GET_MAX_Header(params_package : Package):
    global PARAMS
    global TIME_WINDOW
    global SEQ_WINDOW
    PARAMS.update(functions.get_client_params())
    PARAMS.update({"maximum_msg_size" : params_package.get_payload()})
    print(f" got max size from server: {PARAMS}")
    TIME_WINDOW = float(time.time()) + float(PARAMS["timeout"])
    SEQ_WINDOW = int(PARAMS["window_size"])



def ACK_Header(ack_package : Package):
    global LAST_ACK_SEQ
    global TIME_WINDOW
    global SEQ_WINDOW
    global NO_ACKS

    acked_pack = CURRENT_PACKAGES.get(int(ack_package.payload))
    if acked_pack is not None:
        acked_pack.recvack()
        print(f"received ACK {ack_package.payload}")
        LAST_ACK_SEQ = int(ack_package.payload)
        SEQ_WINDOW = int(PARAMS["window_size"]) + int(ack_package.payload)
        if int(ack_package.payload) + 1 in CURRENT_PACKAGES:
            next_timer = CURRENT_PACKAGES.get(ack_package.get_pos() + 1).get_time()
            TIME_WINDOW = float(PARAMS["timeout"]) + next_timer
        else:
            if int(ack_package.payload) in CURRENT_PACKAGES:
                if CURRENT_PACKAGES.get(int(ack_package.payload)).get_ack_state():
                    print(f"Warning: package {acked_pack.getSeq()} has been acked twice")
                else:
                    print(f"Warning: package {acked_pack.getSeq()} has not been in NO ACK, found in CURRENT PACKAGES")
                    CURRENT_PACKAGES.get(int(ack_package.payload)).recvack()
    else:
        print(f"Warning: No package found for key '{ack_package.payload}'.")


def CLOSE_Header(client_socket : socket.socket):
    print(fr"Closing connection...")
    sleep(1)
    print("\nall packages sent: ")
    for package in CURRENT_PACKAGES:
        print(CURRENT_PACKAGES.get(package))

    client_socket.close()
    sys.exit(0)


def send_CLOSE_msg(client_socket : socket.socket):
    before_closing(client_socket)
    print("finish current transfer:")
    finish_package = Package("DONE", "EOMsg")
    CURRENT_PACKAGES.update({finish_package.getSeq(): finish_package})
    client_socket.send(finish_package.encode_package(int(PARAMS["maximum_msg_size"])))
    while True:
        lost_pack = get_lost_package()
        seconds = float(PARAMS["timeout"])
        while seconds > 0 and lost_pack is not None:
            print(f"Time left: {seconds} seconds")
            time.sleep(0.2)
            seconds -= 0.2
            lost_pack = get_lost_package()
        if lost_pack is not None:
            print(f"lost pack: {get_lost_package().getSeq()}")
            print("resending DONE msg")
            client_socket.send(finish_package.encode_package(int(PARAMS["maximum_msg_size"])))
        else:
            break

    close_package = Package("CLOSE", "request to close connection")
    CURRENT_PACKAGES.update({close_package.getSeq(): close_package})
    client_socket.send(close_package.encode_package(int(PARAMS["maximum_msg_size"])))


def resend_data(package : Package, client_socket):
    print(f"time wind: {TIME_WINDOW} seq win: {SEQ_WINDOW}")
    print(f"RESENDING package :\n {package}")
    time.sleep(0.5)
    CURRENT_PACKAGES.get(package.get_pos()).update_time()
    client_socket.send(package.encode_package(int(PARAMS["maximum_msg_size"])))


def send_data(package : Package, client_socket):
    print(f"time wind: {TIME_WINDOW} seq win: {SEQ_WINDOW}")
    print(f"SENDING package :\n {package}")
    time.sleep(0.5)
    package.update_time()
    CURRENT_PACKAGES.update({int(package.getSeq()): package})
    if int(package.getSeq()) in PACKAGES_TO_LOSE:
        print(f"package {package.getSeq()} will be lost")
        pass
    else:
        client_socket.send(package.encode_package(int(PARAMS["maximum_msg_size"])))


def send_logic(client_socket : socket.socket, sliced_msg : list[bytes]):
    seq =0
    for data_slice in sliced_msg:
        seq+=1
        if check_time_threshold() and check_seq_threshold(seq):
            package = Package("MSG", data_slice.decode("utf-8"))
            print(f"sending package: {package}")
            send_data(package, client_socket)
            time.sleep(0.3)
        else:
            print("resend lost package")
            resend_logic(client_socket)
    before_closing(client_socket)


def resend_logic(client_socket : socket.socket):
    global LAST_ACK_SEQ
    lost_pack = get_lost_package()
    if lost_pack is not None:
        print(f"resending package: {lost_pack}")
        resend_data(lost_pack, client_socket)
        wait_for_ack(client_socket, lost_pack.get_pos())
    else:
        print(f"no lost package found, skipping resend")

def slice_data(data : bytes):
    chunks = []
    for i in range(0, len(data), int(PARAMS["maximum_msg_size"])):
        chunks.append(data[i:i + int(PARAMS["maximum_msg_size"])])
    return chunks


def send_from_text_file(client_socket : socket.socket):
    msg = PARAMS.get("massage")
    print(f"sending msg from file: {msg}")
    sliced_msg = slice_data(msg.encode("utf-8"))
    send_logic(client_socket, sliced_msg)

    send_CLOSE_msg(client_socket)
    time.sleep(1)

def wait_for_ack(client_socket : socket.socket, pos: int):
    global LAST_ACK_SEQ
    LAST_ACK_SEQ = int(pos)
    seconds = float(PARAMS["timeout"])
    while int(LAST_ACK_SEQ) != pos:
        print(f"waiting for ack: {pos}")
        time.sleep(0.3)
        seconds -= 0.3
        if int(LAST_ACK_SEQ) == pos:
            return True
        elif seconds <= 0:
            return False
        else:
            continue
    return True

def all_acks_received():
    global CURRENT_PACKAGES
    return all(pkg.get_ack_state() for pkg in CURRENT_PACKAGES.values())


def before_closing(client_socket : socket.socket):
    print("handling lost packages before close:")
    while not all_acks_received():
        time.sleep(0.5)
        while get_lost_package():
            resend_logic(client_socket)
        else:
            break



def get_lost_package():
    global CURRENT_PACKAGES
    # Find the smallest key where the package has not received an ACK
    for key in sorted(CURRENT_PACKAGES):
        pack = CURRENT_PACKAGES.get(key)
        if not pack.get_ack_state():
            return pack
    return None

def update_window_size(package : Package):
    update_time_window(package)
    update_seq_window(package)
    print(f"updated window size by: {package.getSeq()} "
          f"new seq size: {SEQ_WINDOW}"
          f"\nnew time window: {TIME_WINDOW}")


def update_time_window(package : Package):
    global TIME_WINDOW
    TIME_WINDOW = float(package.get_time()) + float(PARAMS["timeout"])

def update_seq_window(package : Package):
    global SEQ_WINDOW
    SEQ_WINDOW = int(PARAMS["window_size"]) + int(package.getSeq())
    print(f"updating window size by: {package.getSeq()} new seq size: {SEQ_WINDOW}")



def recv_with_timeout(sock, timeout=2.0):
    ready, _, _ = select.select([sock], [], [], timeout)
    if ready:
        return sock.recv(1024)  # Adjust buffer size as needed
    else:
        return None


def main_client():
    client_socket = create_client_socket()

    # Start a thread to handle receiving messages
    Thread(target=receive, args=(client_socket,)).start()
    while PARAMS is None or len(PARAMS) == 0:
        time.sleep(0.5)
    print(PARAMS)

    send_from_text_file(client_socket)

    #client_socket.close()

if __name__ == '__main__':
    main_client()
