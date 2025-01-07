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
from package import Package


HOST = '127.0.0.1'
PORT = 55558

HEADER_SIZE = package.HEADER_SIZE
MAX_MSG_SIZE = 4
BUFSIZ = HEADER_SIZE + MAX_MSG_SIZE
GOT_MAX_SIZE = False

ADDR = (HOST, PORT)
PARAMS : Dict[str,str] ={}
PACKAGES_TO_LOSE = [4,7,10]

CURRENT_PACKAGES : Dict[int,Package]= {}
LAST_ACK_SEQ : int = 0

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
    client_socket.send(Package("GET_MAX", "").encode_package(4))
    data = client_socket.recv(HEADER_SIZE + 4)
    pack_get = Package("TEMP", "")
    pack_get.decode_package(data, 4)
    header = pack_get.get_header()
    if header == "RETURN_MAX":
        done = GET_MAX_Header(params_package=pack_get)
        return done


def receive(client_socket):
    """Continuously listens for messages (or ACKs) from the server."""
    global PARAMS
    global BUFSIZ
    while True:
        try:
            print(f"current buffer : {BUFSIZ}")

            data = client_socket.recv(BUFSIZ)
            new_package = Package("TEMP", " ")
            new_package.decode_package(data, MAX_MSG_SIZE)

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

def check_time_threshold():
    if package is not None:
        if TIME_WINDOW and TIME_WINDOW <= time.time():
            print(f"THRESHOLD PASSED (time): \nTime Window: {TIME_WINDOW}, Current time: {time.time()} ")
            return False
        else:
            return True

def check_seq_threshold(package_seq):
    if package is not None:
        if SEQ_WINDOW and int(SEQ_WINDOW) < int(package_seq):
            print(f"THRESHOLD PASSED (seq): \nSeq Window: {SEQ_WINDOW}, Current pack seq: {package_seq}")
            return False
        else:
            return True


def GET_MAX_Header(params_package : Package):
    global PARAMS
    global TIME_WINDOW
    global SEQ_WINDOW
    global BUFSIZ
    global HEADER_SIZE
    global GOT_MAX_SIZE
    PARAMS.update(functions.get_client_params())
    PARAMS.update({"maximum_msg_size" : params_package.get_payload()})
    print(f" got max size from server: {PARAMS}")
    TIME_WINDOW = float(time.time()) + float(PARAMS["timeout"])
    SEQ_WINDOW = int(PARAMS["window_size"])
    update_buffer_andmax_size(int(PARAMS["maximum_msg_size"]))
    GOT_MAX_SIZE = True
    return True



def ACK_Header(ack_package : Package):
    global LAST_ACK_SEQ
    global TIME_WINDOW
    global SEQ_WINDOW
    acked_pack = CURRENT_PACKAGES.get(int(ack_package.payload))
    if acked_pack is not None:
        LAST_ACK_SEQ = get_last_ack_seq()
        if acked_pack.get_pos() > LAST_ACK_SEQ +1:
            print(f"ACKED PACKAGE OUT OF ORDER: {acked_pack}, acks {[i for i in range(LAST_ACK_SEQ+1, acked_pack.get_pos())]} where lost")
            for i in range(LAST_ACK_SEQ+1, acked_pack.get_pos()):
                next_ack = CURRENT_PACKAGES.get(i)
                print(f"Correcting lost ack {next_ack.get_pos()}")
                next_ack.recvack()

        acked_pack.recvack()

        print(f"\nreceived ACK {ack_package.payload} ! \n")
        update_window_size()
    else:
        print(f"Warning: No package found for key '{ack_package.payload}'.")


def CLOSE_Header(client_socket : socket.socket):
    print(fr"Closing connection...")
    sleep(1)
    print("\nall packages sent: ")
    for seq in CURRENT_PACKAGES:
        print(CURRENT_PACKAGES.get(seq))

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
    print(f"Time wind: {TIME_WINDOW} Seq win: {SEQ_WINDOW}")
    print(f"RESENDING package :\n {package}")
    time.sleep(0.5)
    CURRENT_PACKAGES.get(package.get_pos()).update_time()
    client_socket.send(package.encode_package(int(PARAMS["maximum_msg_size"])))


def send_data(data_slice : str, client_socket):
    global PACKAGES_TO_LOSE
    print(f"Time window: {TIME_WINDOW} Seq window: {SEQ_WINDOW}")
    new_pack = Package("MSG", data_slice)
    print(f"SENDING package :\n {str(new_pack)}")
    time.sleep(0.5)
    CURRENT_PACKAGES.update({int(new_pack.get_pos()): new_pack})
    print(f"added package to current packages: {new_pack}"
          f"current packages state: {[str(pack) for pack in CURRENT_PACKAGES.values()]}")

    if int(new_pack.get_pos()) in PACKAGES_TO_LOSE:
        print(f"package {new_pack.get_pos()} will be lost")
        PACKAGES_TO_LOSE.remove(int(new_pack.get_pos()))
    else:
        client_socket.send(new_pack.encode_package(int(PARAMS["maximum_msg_size"])))


def send_logic(client_socket : socket.socket, sliced_msg : list[bytes]):
    seq =0
    for data_slice in sliced_msg:
        seq+=1
        update_window_size()
        time.sleep(0.3)
        if not check_time_threshold() or not check_seq_threshold(seq):
            print("resend lost package")
            sent = resend_logic(client_socket)
        send_data(data_slice.decode("utf-8"), client_socket)
    before_closing(client_socket)


def resend_logic(client_socket : socket.socket):
    lost_pack = get_lost_package()
    if lost_pack is not None:
        while True:
            print(f"transfer for resending package: {lost_pack}")
            resend_data(lost_pack, client_socket)
            worked = wait_for_ack(lost_pack.get_pos())
            if worked:
                break
        return True
    else:
        print(f"no lost package found, skipping resend")
        return False

def slice_data(data : bytes):
    chunks = []
    for i in range(0, len(data), int(PARAMS["maximum_msg_size"])):
        chunks.append(data[i:i + int(PARAMS["maximum_msg_size"])])
    return chunks


def send_from_text_file(client_socket : socket.socket):
    msg = str(PARAMS.get("massage"))
    print(f"sending msg from file: {msg}")
    sliced_msg = slice_data(msg.encode("utf-8"))
    print(f"sliced msg: {sliced_msg}")
    send_logic(client_socket, sliced_msg)

    send_CLOSE_msg(client_socket)
    time.sleep(1)

def wait_for_ack(pos: int):
    while True:
        last_ack = get_last_ack_seq()
        seconds = float(PARAMS["timeout"])
        print(f"waiting for ack: {pos}")
        while seconds > 0 and int(last_ack) < int(pos):
            print(f"time left: {seconds}", end="")
            time.sleep(0.3)
            seconds -= 0.3
            last_ack = get_last_ack_seq()
            if int(last_ack) >= int(pos):
                return True
            elif seconds <= 0:
                return False
            else:
                continue


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
    print(f"CURRENT PACKAGES: {[str(CURRENT_PACKAGES.get(key)) for key in CURRENT_PACKAGES]}")
    # Find the smallest key where the package has not received an ACK
    for key in sorted(CURRENT_PACKAGES, reverse=False):
        pack = CURRENT_PACKAGES.get(key)
        if not pack.get_ack_state():
            print(f"min pos, no ack: {str(pack)}\n")
            return pack
    return None

def update_window_size():
    print(f"\nupdated window size: ")
    update_time_window()
    update_seq_window()

def update_time_window():
    global TIME_WINDOW
    last_no_ack = get_lost_package()
    if last_no_ack is not None and TIME_WINDOW is not None:
        print(f'Updating TIME window by package {last_no_ack.get_pos()} :\n'
              f'New time window {float(last_no_ack.get_time()) + float(PARAMS["timeout"])}, Prev time window: {TIME_WINDOW}')
        TIME_WINDOW = float(last_no_ack.get_time()) + float(PARAMS["timeout"])
    else:
        print("starting time window based on current time ")
        TIME_WINDOW = float(time.time()) + float(PARAMS["timeout"])


def update_seq_window():
    global SEQ_WINDOW
    last_ack = get_last_ack_seq()
    if last_ack is not None and SEQ_WINDOW is not None:
        print(f'Updating SEQ window size by last acked pack: {last_ack}\n'
              f'New seq window: {int(PARAMS["window_size"]) + int(last_ack)} Prev seq window : {SEQ_WINDOW}\n')
        SEQ_WINDOW = int(PARAMS["window_size"]) + int(last_ack)
    else:
        print("starting seq window based on params ")
        SEQ_WINDOW = int(PARAMS["window_size"])


def get_last_ack_seq():
    for seq in sorted(CURRENT_PACKAGES, reverse=True):
        if CURRENT_PACKAGES.get(seq).get_ack_state():
            return seq
    return 0


def update_buffer_andmax_size(new_max_size):
    global MAX_MSG_SIZE
    global BUFSIZ
    MAX_MSG_SIZE = new_max_size
    BUFSIZ = HEADER_SIZE + MAX_MSG_SIZE
    print(f"updated buffer size to {BUFSIZ} and max size to {MAX_MSG_SIZE}", flush=True)


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
