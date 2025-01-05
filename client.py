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
PORT = 55555
BUFSIZ = 1024
ADDR = (HOST, PORT)
PARAMS : Dict[str,str] ={}
CURRENT_PACKAGES : Dict[int,Package]= {}
NO_ACKS :Dict[int,Package] = {}
LAST_ACK_SEQ : int = 1
PACKAGE_COUNT =1
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
    client_socket.send(Package("GET_MAX", " ").encode_package())



def receive(client_socket):
    """Continuously listens for messages (or ACKs) from the server."""
    global PARAMS
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
    global TIME_WINDOW
    global SEQ_WINDOW
    global NO_ACKS
    try:
        CURRENT_PACKAGES.update({int(package.getSeq()): package})
        NO_ACKS.update({int(package.getSeq()): package})
        if not check_seq_threshold(package):
            print(f"Warning:  seq threshold for package found: "
                  f"\npackage seq: {package.getSeq()}\n"
                  f"Window seq: {SEQ_WINDOW}\n"
                  f"package prev seq: {package.get_prev_seq()}\n"
                  f"handling lost pack:")

            handle_lost_packages(client_socket, None)

        time.sleep(0.1)
        print(f"time wind: {TIME_WINDOW} seq win: {SEQ_WINDOW}")
        print(f"SENDING package :\n {package}")
        client_socket.send(package.encode_package())
        #TIME_WINDOW = package.get_time() + int(PARAMS["timeout"])

    except Exception as e:
        print(f"Error while sending data: {e} package seq {package.getSeq()}")

def resend_data( package: Package, client_socket):
    global CURRENT_PACKAGES
    global TIME_WINDOW
    global SEQ_WINDOW
    global NO_ACKS
    try:
        CURRENT_PACKAGES.update({int(package.getSeq()): package})
        NO_ACKS.update({int(package.getSeq()): package})
        print(f"time wind: {TIME_WINDOW} seq win: {SEQ_WINDOW}")
        print(f"RESENDING package :\n {package}")
        client_socket.send(package.encode_package())

    except Exception as e:
        print(f"Error resending while sending data: {e} package seq {package.getSeq()}")

def handle_lost_packages(client_socket, resend):
    global PACKAGE_COUNT
    global LAST_ACK_SEQ
    global TIME_WINDOW
    global SEQ_WINDOW


    print(f"handling lost package: ")
    if LAST_ACK_SEQ +1 in CURRENT_PACKAGES:
        to_send = CURRENT_PACKAGES.get(LAST_ACK_SEQ +1)
        print(f"found lost pack: to send")
        CURRENT_PACKAGES.update({int(to_send.getSeq()): to_send})
        NO_ACKS.pop(to_send.get_prev_seq())
        NO_ACKS.update({int(to_send.getSeq()): to_send})
        to_send.update_for_resend(PACKAGE_COUNT + 1, to_send.getSeq())
        if LAST_ACK_SEQ + 2 in CURRENT_PACKAGES:
            next_threshold = CURRENT_PACKAGES.get(LAST_ACK_SEQ+2)
            print(f"updating window size by next no ack: {SEQ_WINDOW}")
            update_window_size(next_threshold)
        else:
            print(f"updating window size resend pack:  {SEQ_WINDOW}")
            update_window_size(to_send)

        resend_data(to_send, client_socket)

    






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
    for package in packages_to_send:
        print(f"CREATED package type: {package.get_header()} seq: {package.getSeq()} with DATA: {package.get_payload()}")
    return packages_to_send


def get_lost_packages():
    resend = []
    global NO_ACKS
    if len(NO_ACKS) > 0:
        for seq in NO_ACKS:
            if not check_treshhold(NO_ACKS.get(seq)):
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
    PARAMS.update(params_package.get_params())
    print(PARAMS)
    #PARAMS["timeout"] = str(int(PARAMS["timeout"]))
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
            print(f"Warning: No package found for key '{ack_package.payload}'.")
    else:
        print(f"Warning: No package found for key '{ack_package.payload}'.")


def CLOSE_Header(client_socket : socket.socket):
    print(fr"Closing connection...")
    client_socket.close()
    sys.exit(0)


def send_CLOSE_msg(client_socket : socket.socket):
    before_closing(client_socket)
    close_package = ClosePackage()
    CURRENT_PACKAGES.update({close_package.getSeq(): close_package})
    send_data(close_package, client_socket)


def send_msg_logic(client_socket : socket.socket):
    while True:
        msg = input("\nenter your message: \n")
        if msg == "1":
            send_CLOSE_msg(client_socket = client_socket)
            break
        resend = get_lost_packages()
        if resend and len(resend) > 0:
            print("handling lost packages")
            handle_lost_packages(client_socket, resend)
        sliced_msg = slice_data(msg.encode("utf-8"))
        packages_to_send = create_msg_packages_list(slice_list=sliced_msg)
        for pack in packages_to_send:
            print(f"TRANSFER for send- package type: {pack.get_header()} seq: {pack.getSeq()} with DATA: {pack.get_payload()}")
            send_data(pack, client_socket)
        if all_acks_received():
            finish_package = Package("DONE", "EOMsg", seq=PACKAGE_COUNT)
            PACKAGE_COUNT += 1
            CURRENT_PACKAGES.update({finish_package.getSeq(): finish_package})
            NO_ACKS.update({finish_package.getSeq(): finish_package})
            send_data(finish_package, client_socket)
            break

    print("\nall packages sent: ")
    for package in CURRENT_PACKAGES:
        print(CURRENT_PACKAGES.get(package))

    print("\nno acks received: ")
    for package in NO_ACKS:
        print(NO_ACKS.get(package))


def all_acks_received():
    return all(CURRENT_PACKAGES.get(seq).get_ack_state() for seq in CURRENT_PACKAGES)


def before_closing(client_socket : socket.socket):
    while not all_acks_received():
        time.sleep(0.5)
        try:
            print("handling lost packages")
            resend = get_lost_packages()
            if resend and len(resend) > 0:
                handle_lost_packages(client_socket, resend)
            else:
                print("no lost packages found")
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

def main_client():
    client_socket = create_client_socket()

    # Start a thread to handle receiving messages
    Thread(target=receive, args=(client_socket,)).start()
    if PARAMS is not None:
        print(PARAMS)
        send_msg_logic(client_socket)

    client_socket.close()

if __name__ == '__main__':
    main_client()
