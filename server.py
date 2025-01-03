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
PORT = 55555
BUFSIZ = 1024
MAX_CLIENTS = 5
ADDR = (HOST, PORT)
CLIENTS = []
PARAMS = functions.get_params()
print(PARAMS)
LOSE_THOSE_PACKAGE = [3,4,5,8,10,12]
LAST_SEQ=1




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

                new_package = Package(" ", " ")
                new_package.decode_package(data)

                header = new_package.get_header()

                if header == "GET_MAX":
                    GET_MAX_Header(client_socket= CLIENT_SOCKET)

                elif header == "MSG":
                    MSG_Header(client_socket= CLIENT_SOCKET,msg_package= new_package, lose_those_package=LOSE_THOSE_PACKAGE)

                elif header == "CLOSE":
                    CLOSE_Header(client_socket= CLIENT_SOCKET, client_address=client_address)
                    break

                elif not data:
                    print(f"Client {client_address} forcibly closed the connection", flush=True)
                    CLOSE_Header(client_socket= CLIENT_SOCKET, client_address=client_address)
                    break

                else:
                    print(f"Undetected header: \nRaw data received from {client_address}: {data}", flush=True)

            except OSError as e:
                # Check if the error is specifically WinError 10054
                if hasattr(e, 'winerror') and e.winerror == 10054:
                    print(f"Client {client_address} forcibly closed the connection", flush=True)
                    CLOSE_Header(client_socket= CLIENT_SOCKET, client_address=client_address)
                    break
                else:
                    print(f"Error with client {client_address}: {e}", flush=True)
                    CLOSE_Header(client_socket= CLIENT_SOCKET, client_address=client_address)
                    break
            except Exception as ex:
                print(f"Error while handling client {client_address}: {ex}", flush=True)
    except Exception as ex:
        print(f"Error while handling client {client_address}: {ex}", flush=True)


def GET_MAX_Header(client_socket : socket.socket):
    new_package = GetPackage(PARAMS)
    client_socket.send(new_package.encode_package())


def MSG_Header(client_socket : socket.socket, msg_package : Package, lose_those_package : List[int] = None):
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
                if LAST_SEQ +1 != msg_package.getSeq():
                    print(f"package {msg_package.getSeq()} lost", flush=True)
                    while LAST_SEQ +1 != msg_package.getSeq():
                        next_acks.append(AckPackage(msg_package))
                        data = client_socket.recv(BUFSIZ)
                        msg_package = Package(" ", " ")
                        msg_package.decode_package(data)
                    for msg_package in next_acks:
                        msg_package.send_ack(client_socket)
                        print(f"ACK for package {msg_package.getSeq()}", flush=True)
                    next_acks.clear()

                msg.append(msg_package)
                LAST_SEQ = int(msg_package.getSeq())
                msg_package.send_ack(client_socket)
                if msg_package.get_header() == "DONE":
                    print("DONE")
                    MSG_DONE_Header(msg=msg, client_socket=client_socket, msg_package=msg_package)
                    break

            data = client_socket.recv(BUFSIZ)
            msg_package = Package(" ", " ")
            msg_package.decode_package(data)

        except Exception as e:
            print(f"Error while handling msg: {e}", flush=True)
            break


def CLOSE_Header(client_socket : socket.socket, client_address):
    print(f"Client {client_address} disconnected", flush=True)
    client_socket.close()
    CLIENTS.remove(client_address)


def MSG_DONE_Header(msg : List[Package], client_socket : socket.socket, msg_package : Package):
    msg_package.send_ack(client_socket)
    str_msg = ""
    msg.sort(key=lambda package: package.getSeq())
    print(f"{pack.get_payload()} , " for pack in msg)
    for pack in msg:
        str_msg += pack.get_payload()
    print("")
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
        threading.excepthook = my_excepthook

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

