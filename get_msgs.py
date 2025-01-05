
"""
def send_msg_logic(client_socket : socket.socket):
    while True:
        msg = input("\nenter your message: \n")
        if msg == "1":
            send_CLOSE_msg(client_socket = client_socket)
            break
        handle_lost_packages(client_socket)
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
"""