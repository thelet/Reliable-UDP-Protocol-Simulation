
import socket
import threading

from socket import AF_INET, SOCK_STREAM
from threading import Thread

from typing import List

import functions
import package



from package import Package



HOST = '127.0.0.1'
PORT = 55558


MAX_CLIENTS = 1
ADDR = (HOST, PORT)
CLIENTS = [4,9,10]
PARAMS = functions.get_server_params()
print(PARAMS)
MAX_MSG_SIZE = 4
LAST_SEQ=0
HEADER_SIZE = package.HEADER_SIZE
BUFSIZ = HEADER_SIZE + MAX_MSG_SIZE
ACKS_TO_LOSE = [0]


def create_server_socket():
    try:
        SERVER_SOCKET = socket.socket(AF_INET, SOCK_STREAM)
        SERVER_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        SERVER_SOCKET.bind(ADDR)
        SERVER_SOCKET.listen(MAX_CLIENTS)
        print("creating server....")
        return SERVER_SOCKET

    except Exception as e:
        print(f"Error while creating the server: {e}")


def accept_incoming_connections(server_socket : socket.socket):
    """Sets up handling for incoming clients."""
    print("wating for connections....")
    global CLIENTS
    CLIENTS.clear()
    try:
        while True:
            try:
                client, client_address = server_socket.accept()
                if client_address not in CLIENTS:
                    CLIENTS.append(client_address)
                    print(f"{client_address} has connected.", flush=True)
                    # Handle the client in a separate thread

                    client_THREAD = Thread(target=handle_client, args=(client,client_address))
                    client_THREAD.start()
                else:
                    print("Already connected.", flush=True)
                    break

            except OSError as e:
                if hasattr(e, 'winerror') and e.winerror == 10054:
                    print(f"Client: forcibly closed the connection", flush=True)
                else:
                    print(f"Error while connecting to client: {e}", flush=True)
                break

    except Exception as e:
        print(f"Error while connecting to client: {e}", flush=True)



def handle_client(CLIENT_SOCKET, client_address):
    global MAX_MSG_SIZE
    print(f"Handling client {client_address}", flush=True)
    done= initial_connection(CLIENT_SOCKET, client_address)
    if done:
        update_buffer_andmax_size(int(PARAMS["maximum_msg_size"]))
    try:
        while True:
            try:
                data = CLIENT_SOCKET.recv(BUFSIZ)
                if not data:
                    print(f"Client {client_address} forcibly closed the connection", flush=True)
                    CLOSE_Header(client_socket= CLIENT_SOCKET, client_address=client_address)
                    break

                new_package = Package("TEMP", " ")
                print(f"current max size: {MAX_MSG_SIZE}")
                new_package.decode_package(data, MAX_MSG_SIZE)
                header = new_package.get_header()

                if header == "GET_MAX":
                    print(f"GET_MAX from {client_address}")
                    GET_MAX_Header(client_socket= CLIENT_SOCKET)

                elif header == "MSG" or header == "DONE":
                    print(f"MSG from {client_address}, starting to receive:")
                    MSG_Header(client_socket= CLIENT_SOCKET,msg_package= new_package, client_address= client_address)

                elif header == "CLOSE":
                    print(f"CLOSE request from {client_address}")
                    CLOSE_Header(client_socket= CLIENT_SOCKET, client_address=client_address)
                    break

                else:
                    print(f"Undetected header: \nRaw data received from {client_address}: {data}", flush=True)
                    pass

            except OSError as e:
                # Check if the error is specifically WinError 10054- means that client disconnected without sending CLOSE package
                if hasattr(e, 'winerror') and e.winerror == 10054:
                    print(f"Client {client_address} forcibly closed the connection", flush=True)
                    break
                else:
                    print(f"Error with client {client_address}: {e}", flush=True)
                    break
    except OSError as ex:
        print(f"Error while handling client {client_address}: {ex}", flush=True)



def GET_MAX_Header(client_socket : socket.socket):
    global MAX_MSG_SIZE
    try:
        new_package = Package("RETURN_MAX", PARAMS["maximum_msg_size"])
        print(f"SENDING max size package :\n {new_package}")
        client_socket.send(new_package.encode_package(4))
        return True
    except Exception as e:
        print(f"Error while sending max size package: {e}", flush=True)



def MSG_Header(client_socket : socket.socket, msg_package : Package, client_address = None):
    last_seq = int(msg_package.get_pos()) -1
    msg_list = []
    full_msg = []
    global ACKS_TO_LOSE
    while msg_package.get_header() == "MSG":
        try:
            print(f"received package: {msg_package} last_seq = {last_seq}")
            msg_list.append(msg_package)
            msg_list.sort(key=lambda package: package.get_pos())

            for pack in msg_list:
                if int(pack.get_pos()) == last_seq +1:
                    print(f"sending ack for pack: {pack}")
                    if int(pack.get_pos()) in ACKS_TO_LOSE:
                        ACKS_TO_LOSE.remove(int(pack.get_pos()))
                    else:
                        pack.send_ack(client_socket, PARAMS["maximum_msg_size"])
                    last_seq = pack.get_pos()
                    full_msg.append(pack)

            for pack in full_msg:
                if pack in msg_list:
                    msg_list.remove(pack)

            data = client_socket.recv(BUFSIZ)
            msg_package = Package("TEMP", " ")
            msg_package.decode_package(data, PARAMS["maximum_msg_size"])
        except Exception as e:
            print(f"Error while receiving MSG data: {e}", flush=True)
            break

    if msg_package.get_header() == "DONE":
        print(f"done sending file")
        if msg_list or len(msg_list) > 0:
            print(f"warning! lost data: {[pack.get_payload() for pack in msg_list]}")
        MSG_DONE_Header(client_socket, msg_package, full_msg)

    elif msg_package.get_header() == "CLOSE":
        print(f"Warning! client {client_address} sent CLOSE package before DONE package, closing connection.")
        CLOSE_Header(client_socket= client_socket, client_address=client_address)

    else:
        print(f"Undetected header: \nPackage received from {client_address}: {msg_package}", flush=True)




def CLOSE_Header(client_socket : socket.socket, client_address):
    print(f"Client {client_address} disconnected", flush=True)
    client_socket.send(Package("DISCONNECT", "approving client disconnection").encode_package(int(PARAMS["maximum_msg_size"])))
    client_socket.close()
    CLIENTS.remove(client_address)


def MSG_DONE_Header(client_socket : socket.socket, msg_package : Package, msg : List[Package]):
    if msg_package:
        msg_package.send_ack(client_socket, PARAMS["maximum_msg_size"])
    str_msg = ""
    if msg:
        msg.sort(key=lambda package: package.get_pos())
        print(f"msg packages: {[pack.get_payload() for pack in msg]}")
        for pack in msg:
            str_msg += pack.get_payload()
        print("\n full message received: ")
        print(str_msg)
        print("")

def my_excepthook(exc):
    """
    Example excepthook function.
    This is called if a thread raises an unhandled exception.
    'exc' is a threading.ExceptHookArgs object (Python 3.8+).
    """
    print(f"Thread {exc.thread.name} encountered an exception: "
          f"{exc.exc_type.__name__}: {exc.exc_value}", flush=True)

def update_buffer_andmax_size(new_max_size):
    global MAX_MSG_SIZE
    global BUFSIZ
    MAX_MSG_SIZE = new_max_size
    BUFSIZ = HEADER_SIZE + MAX_MSG_SIZE
    print(f"updated buffer size to {BUFSIZ} and max size to {MAX_MSG_SIZE}", flush=True)

def initial_connection(client_socket : socket.socket, client_address):
    data = client_socket.recv(HEADER_SIZE + 4)
    pack_get = Package("TEMP", "")
    pack_get.decode_package(data, 4)
    header = pack_get.get_header()
    if header == "GET_MAX":
        print(f"GET_MAX from {client_address}")
        done = GET_MAX_Header(client_socket=client_socket)
        return done


def main():
    try:
        # Assign the global excepthook for threads
        #threading.excepthook = my_excepthook

        print("Server is starting...", flush=True)
        server_socket = create_server_socket()
        print("Waiting for connection...", flush=True)

        ACCEPT_THREAD = Thread(target=accept_incoming_connections,
                               args=(server_socket,),
                               name="AcceptThread")
        ACCEPT_THREAD.start()

        # Keep the main thread alive
        try:
            while True:
                pass
        except KeyboardInterrupt:
            print("Shutting down server...", flush=True)
        except Exception as e:
            print(f"Error in main loop: {e}", flush=True)

    except Exception as e:
        print(f"Exception in main: {e}", flush=True)



if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Server encountered an error: {e}", flush=True)

