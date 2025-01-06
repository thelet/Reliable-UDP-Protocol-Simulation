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
PORT = 55557
BUFSIZ = 44
ADDR = (HOST, PORT)
PARAMS : Dict[str,str] ={}
CURRENT_PACKAGES : Dict[int,Package]= {}
NO_ACKS :Dict[int,Package] = {}
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


def send_data(package : Package, client_socket):
    global TIME_WINDOW
    global SEQ_WINDOW
    global NO_ACKS
    try:
        time.sleep(0.2)
        package.update_time()
        CURRENT_PACKAGES.update({int(package.getSeq()): package})
        NO_ACKS.update({int(package.getSeq()): package})
        if not check_seq_threshold(package):
            print(f"Warning:  seq threshold for package found: "
                  f"\npackage seq: {package.getSeq()}\n"
                  f"Window seq: {SEQ_WINDOW}\n"
                  f"package prev seq: {package.get_prev_seq()}\n"
                  f"handling lost pack:")

            handle_lost_packages(client_socket, None)
        if not check_time_threshold(package):
            print(f"Warning:  time threshold for package found: "
                  f"\npackage time: {package.get_time()}\n"
                  f"Window time: {TIME_WINDOW}\n"
                  f"package prev seq: {package.get_prev_seq()}\n"
                  f"handling lost pack:")
            handle_lost_packages(client_socket, None)

        print(f"time wind: {TIME_WINDOW} seq win: {SEQ_WINDOW}")
        print(f"SENDING package :\n {package}")
        package.update_time()
        client_socket.send(package.encode_package(int(PARAMS["maximum_msg_size"])))
        #TIME_WINDOW = package.get_time() + int(PARAMS["timeout"])

    except OSError as e:
        print(f"Error while sending data: {e} package seq {package.getSeq()}")


def resend_data( to_resend: Package, client_socket):
    global CURRENT_PACKAGES
    global TIME_WINDOW
    global SEQ_WINDOW
    global NO_ACKS
    try:
        package = to_resend.get_package_for_resend(to_resend.getSeq(), to_resend.get_pos())
        CURRENT_PACKAGES.update({int(package.getSeq()): package})
        NO_ACKS.update({int(package.getSeq()): package})
        print(f"time wind: {TIME_WINDOW} seq win: {SEQ_WINDOW}")
        print(f"RESENDING package :\n {package}")
        client_socket.send(package.encode_package(int(PARAMS["maximum_msg_size"])))

    except Exception as e:
        print(f"Error resending while sending data: {e} package seq {package.getSeq()}")


def handle_lost_packages(client_socket, resend):
    global LAST_ACK_SEQ
    global TIME_WINDOW
    global SEQ_WINDOW
    print(f"handling lost package: ")
    if LAST_ACK_SEQ +1 in CURRENT_PACKAGES:
        lost_pack = CURRENT_PACKAGES.get(LAST_ACK_SEQ +1)
        to_send = lost_pack.get_package_for_resend(prev_seq= lost_pack.getSeq(), prev_pos= lost_pack.get_pos())
        print(f"found lost pack: {to_send}")
        CURRENT_PACKAGES.update({int(to_send.getSeq()): to_send})
        if to_send in NO_ACKS:
            NO_ACKS.pop(int(to_send.get_prev_seq()))
        else:
            print(f"Warning: package {to_send.getSeq()} has not been in NO ACK, found in CURRENT PACKAGES")
        NO_ACKS.update({int(to_send.getSeq()): to_send})

        if LAST_ACK_SEQ + 2 in CURRENT_PACKAGES:
            next_threshold = CURRENT_PACKAGES.get(LAST_ACK_SEQ+2)
            print(f"updating window size by next no ack:")
            update_window_size(next_threshold)
        else:
            print(f"updating window size resend pack:")
            update_window_size(to_send)

        resend_data(to_send, client_socket)

    

def slice_data(data : bytes):
    chunks = []
    for i in range(0, len(data), int(PARAMS["maximum_msg_size"])):
        chunks.append(data[i:i + int(PARAMS["maximum_msg_size"])])
    return chunks


def create_msg_packages_list(slice_list : list[bytes]):
    packages_to_send = []
    for data_slice in slice_list:
        package = Package("MSG", data_slice.decode("utf-8"))
        packages_to_send.append(package)
    for package in packages_to_send:
        print(f"CREATED package type: {package.get_header()} seq: {package.getSeq()} with DATA: {package.get_payload()}")
    return packages_to_send


def get_lost_packages():
    resend : List[Package] = []
    global NO_ACKS
    if len(NO_ACKS) > 0:
        for seq in NO_ACKS:
            resend.append(NO_ACKS.get(seq))
            print(f"found lost package: {NO_ACKS.get(seq)}")
    return resend


def check_treshhold(package : Package):
    return  check_time_threshold(package) and check_seq_threshold(package)

def check_time_threshold(package : Package):
    if package is not None:
        if TIME_WINDOW and TIME_WINDOW <= time.time():
            print(f"time threshold passed: \ncurrent time: {time.time()} current pack time: {package.get_time()} diff: {int(time.time()) - int(package.get_time())} )")
            return False
        else:
            return True

def check_seq_threshold(package : Package):
    global LAST_ACK_SEQ
    if package is not None:
        if SEQ_WINDOW and SEQ_WINDOW < package.getSeq():
            print(
                f"window size threshold passed: \nwindow size: {SEQ_WINDOW} current pack number: {package.getSeq()} diff: {int(package.getSeq()) - int(LAST_ACK_SEQ)} ")
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
    print(f"received ACK {ack_package.payload}")
    acked_pack = CURRENT_PACKAGES.get(int(ack_package.payload))
    if acked_pack is not None:
        acked_pack.recvack()
        LAST_ACK_SEQ = int(ack_package.payload)
        SEQ_WINDOW = int(PARAMS["window_size"]) + int(ack_package.payload)
        if int(ack_package.payload) + 1 in CURRENT_PACKAGES:
            next_timer = CURRENT_PACKAGES.get(ack_package.getSeq() + 1).get_time()
            TIME_WINDOW = float(PARAMS["timeout"]) + next_timer
        if int(ack_package.payload) in NO_ACKS:
            NO_ACKS.pop(int(ack_package.payload))

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

    print("\nno acks received: ")
    for package in NO_ACKS:
        print(NO_ACKS.get(package))
    client_socket.close()
    sys.exit(0)


def send_CLOSE_msg(client_socket : socket.socket):
    before_closing(client_socket)
    print("finish current transfer:")
    finish_package = Package("DONE", "EOMsg")
    CURRENT_PACKAGES.update({finish_package.getSeq(): finish_package})
    NO_ACKS.update({finish_package.getSeq(): finish_package})
    client_socket.send(finish_package.encode_package(int(PARAMS["maximum_msg_size"])))
    while True:
        seconds = float(PARAMS["timeout"])
        while seconds > 0 and NO_ACKS and len(NO_ACKS) > 0:
            print(f"Time left: {seconds} seconds")
            time.sleep(0.2)
            seconds -= 0.2
        if  NO_ACKS and len(NO_ACKS) > 0:
            print(NO_ACKS.get(seq) for seq in NO_ACKS)
            print("resending DONE msg")
            client_socket.send(finish_package.encode_package(int(PARAMS["maximum_msg_size"])))
        else:
            break
    close_package = Package("CLOSE", "request to close connection")
    CURRENT_PACKAGES.update({close_package.getSeq(): close_package})
    client_socket.send(close_package.encode_package(int(PARAMS["maximum_msg_size"])))




def send_package_list(client_socket : socket.socket, package_list : list[Package]):
    for package in package_list:
        send_data(package, client_socket)


def send_msg_logic(client_socket : socket.socket):
    """
       while True:
        msg = input("\nenter your message: \n")
        if msg == "1":
            print("sending close msg...")
            send_CLOSE_msg(client_socket = client_socket)
            break

        sliced_msg = slice_data(msg.encode("utf-8"))
        packages_to_send = create_msg_packages_list(slice_list=sliced_msg)
        for pack in packages_to_send:
            print(f"TRANSFER for send- package type: {pack.get_header()} seq: {pack.getSeq()} with DATA: {pack.get_payload()}")
            send_data(pack, client_socket)


        print("finish current transfer:")
        finish_package = Package("DONE", "EOMsg")
        CURRENT_PACKAGES.update({finish_package.getSeq(): finish_package})
        NO_ACKS.update({finish_package.getSeq(): finish_package})
        send_data(finish_package, client_socket)
    """



def send_from_text_file(client_socket : socket.socket):
    msg = PARAMS.get("massage")
    print(f"sending msg from file: {msg}")
    sliced_msg = slice_data(msg.encode("utf-8"))
    packages_to_send = create_msg_packages_list(slice_list=sliced_msg)
    for pack in packages_to_send:
        print(f"TRANSFER for send- package type: {pack.get_header()} seq: {pack.getSeq()} with DATA: {pack.get_payload()}")
        send_data(pack, client_socket)

    send_CLOSE_msg(client_socket)
    time.sleep(1)



def all_acks_received():
    global NO_ACKS
    return len(NO_ACKS) == 0


def before_closing(client_socket : socket.socket):
    print("handling lost packages before close:")
    while not all_acks_received():
        time.sleep(0.5)
        try:
            if NO_ACKS and len(NO_ACKS) > 0:
                next = min(NO_ACKS.keys())
                to_send = NO_ACKS.get(next)
                if not check_treshhold(to_send):
                    NO_ACKS.pop(next)
                    resend_data(to_send, client_socket)
                else:
                    print("waiting for threshold to pass")
            else:
                break
        except OSError as e:
            print(f"Error while sending last data, closing connection : {e}", flush=True)
            break


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
