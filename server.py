import sys
import socket
from pickle import GLOBAL
from socket import AF_INET, SOCK_STREAM
from threading import Thread
from time import sleep
from typing import List

import functions
from functions import get_from_file, get_from_user, get_params
import threading

from package import Package, GetPackage, AckPackage



HOST = '127.0.0.1'
PORT = 55557
BUFSIZ = 44
MAX_CLIENTS = 5
ADDR = (HOST, PORT)
CLIENTS = []
PARAMS = functions.get_server_params()
print(PARAMS)
MAX_MSG_SIZE = PARAMS["maximum_msg_size"]
LOSE_THOSE_PACKAGE = [3,9,14]
LAST_SEQ=0
HEADER_SIZE = 30





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

            except Exception as e:
                print(f"Error while connecting to client: {e}", flush=True)
                break
    except Exception as e:
        print(f"Error while connecting to client: {e}", flush=True)



def handle_client(CLIENT_SOCKET, client_address):

    print(f"Handling client {client_address}", flush=True)

    try:
        while True:
            try:
                data = CLIENT_SOCKET.recv(BUFSIZ)

                if not data:
                    print(f"Client {client_address} forcibly closed the connection", flush=True)
                    CLOSE_Header(client_socket= CLIENT_SOCKET, client_address=client_address)
                    break

                new_package = Package("TEMP", " ")
                new_package.decode_package(data, PARAMS["maximum_msg_size"])

                header = new_package.get_header()

                if header == "GET_MAX":
                    print(f"GET_MAX from {client_address}")
                    GET_MAX_Header(client_socket= CLIENT_SOCKET)

                elif header == "MSG" or header == "DONE":
                    MSG_Header(client_socket= CLIENT_SOCKET,msg_package= new_package, lose_those_package=LOSE_THOSE_PACKAGE, client_address= client_address)

                elif header == "CLOSE":
                    CLOSE_Header(client_socket= CLIENT_SOCKET, client_address=client_address)
                    break

                else:
                    print(f"Undetected header: \nRaw data received from {client_address}: {data}", flush=True)
                    pass

            except OSError as e:
                # Check if the error is specifically WinError 10054
                if hasattr(e, 'winerror') and e.winerror == 10054:
                    print(f"Client {client_address} forcibly closed the connection", flush=True)
                    #CLOSE_Header(client_socket= CLIENT_SOCKET, client_address=client_address)
                    break
                else:
                    print(f"Error with client {client_address}: {e}", flush=True)
                    CLOSE_Header(client_socket= CLIENT_SOCKET, client_address=client_address)
                    break
            except WindowsError as ex:
                print(f"Error while handling client {client_address}: {ex}", flush=True)
    except OSError as ex:
        print(f"Error while handling client {client_address}: {ex}", flush=True)



def GET_MAX_Header(client_socket : socket.socket):
    global BUFSIZ
    new_package = Package("RETURN_MAX", PARAMS["maximum_msg_size"])
    print(f"SENDING max size package :\n {new_package}")
    #BUFSIZ = int(PARAMS["maximum_msg_size"] + HEADER_SIZE)
    client_socket.send(new_package.encode_package(int(PARAMS["maximum_msg_size"])))



def MSG_Header(client_socket : socket.socket, msg_package : Package, lose_those_package : List[int] = None, client_address = None):
    msg =[]
    next_acks = []
    global LAST_SEQ
    while True:
        try:
            print(f"LOSE_THOSE_PACKAGE: {lose_those_package}", flush=True)
            if int(msg_package.getSeq()) in lose_those_package:
                print(f"losing package {msg_package.getSeq()}", flush=True)
                lose_those_package.remove(int(msg_package.getSeq()))
            else:
                print(f"LAST_SEQ: {LAST_SEQ} current seq: {msg_package.get_pos()}")
                if int(LAST_SEQ) +1 != int(msg_package.get_pos()):
                    print(f"package {int(LAST_SEQ) +1} lost", flush=True)
                    while LAST_SEQ+1 != int(msg_package.get_pos()):
                        print(f"LAST_SEQ: {LAST_SEQ} current seq: {msg_package.get_pos()}")
                        next_acks.append(msg_package)
                        data = client_socket.recv(BUFSIZ)
                        msg_package = Package("TEMP", " ")
                        msg_package.decode_package(data, PARAMS["maximum_msg_size"])
                    next_acks.sort(key=lambda package: package.get_pos())
                    LAST_SEQ = next_acks[-1].get_pos()
                    for msg_package in next_acks:
                        msg_package.send_ack(client_socket, PARAMS["maximum_msg_size"])

                        print(f"data received: {msg_package.payload}")
                        print(f"ACK for package {msg_package.getSeq()}", flush=True)
                    next_acks.clear()
                else:
                    LAST_SEQ += 1

                msg.append(msg_package)
                LAST_SEQ = int(msg_package.getSeq())
                msg_package.send_ack(client_socket,PARAMS["maximum_msg_size"])
                print(f"data received: {msg_package.payload}")
                if msg_package.get_header() == "DONE":
                    print("DONE")
                    MSG_DONE_Header(msg=msg, client_socket=client_socket, msg_package=msg_package)
                    break

            data = client_socket.recv(BUFSIZ)
            msg_package = Package("TEMP", " ")
            msg_package.decode_package(data, PARAMS["maximum_msg_size"])
            if(msg_package.get_header() == "CLOSE"):
                CLOSE_Header(client_socket,client_address=client_address)

        except OSError as e:
            print(f"Error while handling msg: {e}", flush=True)
            break



def CLOSE_Header(client_socket : socket.socket, client_address):
    print(f"Client {client_address} disconnected", flush=True)
    client_socket.send(Package("DISCONNECT", "approving client disconnection").encode_package(int(PARAMS["maximum_msg_size"])))
    client_socket.close()
    CLIENTS.remove(client_address)


def MSG_DONE_Header(msg : List[Package], client_socket : socket.socket, msg_package : Package):
    msg_package.send_ack(client_socket, PARAMS["maximum_msg_size"])
    str_msg = ""
    msg.sort(key=lambda package: package.get_pos())
    print(f"{pack.get_payload()} , " for pack in msg)
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

