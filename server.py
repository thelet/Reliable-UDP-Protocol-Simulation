
import socket
from multiprocessing.pool import CLOSE
from socket import AF_INET, SOCK_STREAM
from threading import Thread
from time import sleep

from Tools.scripts.generate_opcode_h import header

import functions
from functions import get_from_file, get_from_user, get_params

from package import Package, GetPackage, AckPackage

########################################
# הגדרה גלובלית של המשתנים
########################################

HOST = '127.0.0.1'
PORT = 33002
BUFSIZ = 1024
MAX_CLIENTS = 5 #המספר המקסימלי של לקוחות שהשרת יכול לטפל בהם במקביל
ADDR = (HOST, PORT)
CLIENTS = []
PARAMS = functions.get_params()
print(PARAMS)
LOSE_THOSE_PACKAGE = {3,4,5,8,10,12}

########################################
# פתיחה של ה SOCKET
########################################

def create_server_socket():
    SERVER_SOCKET = socket.socket(AF_INET, SOCK_STREAM)
    SERVER_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    SERVER_SOCKET.bind(ADDR)
    SERVER_SOCKET.listen(MAX_CLIENTS)

    return SERVER_SOCKET

########################################
# חיבור ל CLIENT ופתיחה של THREAD
#כל THREAD מטפל בכל לקוח בנפרד
########## ##############################
def accept_incoming_connections(server_socket : socket.socket):
    """Sets up handling for incoming clients."""
    while True:
        try:
            client, client_address = server_socket.accept()
            if client_address not in CLIENTS:
                CLIENTS.append(client_address)
                print(f"{client_address} has connected." , flush=True)
                # Handle the client in a separate thread
                client_THREAD = Thread(target=handle_client, args=(client,client_address))
                client_THREAD.start()
            else:
                print("Already connected.", flush=True)
                pass

        except Exception as e:
            print(f"{e}", flush=True)
            break


########################################
# פונקציה שמטפלת בקבלת המידע מכל לקוח
########## ##############################
def handle_client(CLIENT_SOCKET, client_address):
    print(f"Handling client {client_address}", flush=True)
    while True:
        msg = []
        try:
            data = CLIENT_SOCKET.recv(BUFSIZ)

            new_package = Package(" ", " ")
            new_package.decode_package(data)

            header = new_package.get_header()

            if header == "GET_MAX":
                GET_MAX_Header(client_socket= CLIENT_SOCKET)

            elif header == "MSG":
                MSG_Header(client_socket= CLIENT_SOCKET, msg_package=new_package, lose_package= True)

            elif header == "CLOSE":
                CLOSE_Header(client_socket= CLIENT_SOCKET, client_address=client_address)
                break

            elif not data:
                print(f"Client {client_address} forcibly closed the connection", flush=True)
                CLOSE_Header(client_socket= CLIENT_SOCKET, client_address=client_address)
                break

            else:
                print(f"Undetected header: \nRaw data received from {client_address}: {data}", flush=True)
            #handle_data(data, CLIENT_SOCKET, client_address)

        except OSError as e:
            # Check if the error is specifically WinError 10054
            if hasattr(e, 'winerror') and e.winerror == 10054:
                print(f"Client {client_address} forcibly closed the connection", flush=True)
            else:
                print(f"Error with client {client_address}: {e}", flush=True)
            CLOSE_Header(client_socket= CLIENT_SOCKET, client_address=client_address)
            break



########################################
# פונקציה שמטפלת במידע שהלקוח קיבל
########## ##############################
def handle_data(data, CLIENT_SOCKET,client_address):
    CLIENT_SOCKET.send(f"server received msg: {data.decode()} from ( {client_address[0]} : {client_address[1]} )".encode())

def GET_MAX_Header(client_socket : socket.socket):
    new_package = GetPackage(PARAMS)
    client_socket.send(new_package.encode_package())

def MSG_Header(client_socket : socket.socket, msg_package : Package, lose_package : bool):
    global LOSE_THOSE_PACKAGE
    msg =[]
    while True:
        if lose_package:
            if int(msg_package.getSeq()) not in LOSE_THOSE_PACKAGE:
                msg.append(msg_package)
                msg_package.send_ack(client_socket)
            else:
                LOSE_THOSE_PACKAGE.remove(int(msg_package.getSeq()))
        data = client_socket.recv(BUFSIZ)
        msg_package = Package(" ", " ")
        msg_package.decode_package(data)
        if msg_package.get_header() == "DONE":
            print("DONE", flush=True)
            msg_package.send_ack(client_socket)
            str_msg = ""
            #msg.sort(key=lambda package: package.getSeq())
            for pack in msg:
                str_msg += pack.get_payload()
            print("")
            print(str_msg)
            print("")
            break

def CLOSE_Header(client_socket : socket.socket, client_address):
    print(f"Client {client_address} disconnected", flush=True)
    client_socket.close()
    CLIENTS.remove(client_address)

def main():
    print("Server is starting...", flush=True)
    server_socket = create_server_socket()
    print("Waiting for connection...", flush=True)
    ACCEPT_THREAD = Thread(target=accept_incoming_connections, args=(server_socket,))
    ACCEPT_THREAD.start()
    ACCEPT_THREAD.join()



if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Server encountered an error: {e}", flush=True)
