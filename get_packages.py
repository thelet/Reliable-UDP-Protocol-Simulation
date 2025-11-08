import json

from package import Package 

def extract_seq_payload_dict(json_file_path):
    """
    Reads a Wireshark JSON export and returns a dictionary where:
      - key   = the integer TCP sequence number (or seq-1, seq-2, etc. if duplicates)
      - value = the payload (raw bytes) from the 'data' layer

    :param json_file_path: Path to the .json file exported by Wireshark.
    :return: A dict with keys as either seq_num (int) or string "seq-num" if a duplicate,
             and values as the payload in bytes.
    """
    seq_payload_dict = {}

    with open(json_file_path, 'r', encoding='utf-8') as f:
        packets = json.load(f) 

        for packet in packets:
            try:
                layers = packet["_source"]["layers"]

                # 1) Check if there's a TCP layer and a data layer
                if "tcp" in layers and "data" in layers:
                    # Extract the sequence number (string). Convert to int.
                    seq_str = layers["tcp"].get("tcp.seq")
                    if seq_str is None:
                        # No valid seq? skip
                        print("No valid seq in packet.")
                        continue
                    seq_num = int(seq_str)

                    # Extract the payload in hex (e.g., "47:45:54:5f:4d...")
                    hex_string = layers["data"].get("data.data")
                    if not hex_string:
                        # If there's no actual data, skip
                        print(f"No valid hex payload for seq={seq_num}.")
                        continue

                    # Convert the hex-string to raw bytes
                    try:
                        byte_values = [int(h, 16) for h in hex_string.split(":")]
                    except ValueError as e:
                        # Malformed hex string
                        print(f"Skipping malformed hex for seq={seq_num}: {hex_string}")
                        continue
                    payload_bytes = bytes(byte_values)

                    # Check for collisions in seq_payload_dict
                    if seq_num not in seq_payload_dict:
                        # No collision, store directly
                        seq_payload_dict[seq_num] = payload_bytes
                    else:
                        # Collision found, generate a suffix
                        # e.g., if key '100' exists, next is "100-2", then "100-3", etc.
                        i = 2
                        new_key = f"{seq_num}-{i}"
                        while new_key in seq_payload_dict:
                            i += 1
                            new_key = f"{seq_num}-{i}"

                        seq_payload_dict[new_key] = payload_bytes

            except (KeyError, ValueError) as e:
                # If any structure is missing or conversion fails, just skip
                print(f"Skipping packet due to error: {e}")
                continue

    return seq_payload_dict

# Example usage:
if __name__ == "__main__":
    # Replace with the path to your JSON file
    json_file = r"C:\Users\thele\Documents\EX3\wireshark\5_json.json"
    seq_dict = extract_seq_payload_dict(json_file)

    # Print each sequence and its payload in hex
    for seq, payload in seq_dict.items():
        print(f"Key: {seq}, Payload (hex): {payload.hex()}", end="")

        # Optionally, decode as a Package if you have a decode method
        temp_pack = Package("TEMP", " ")
        
        try:
            temp_pack.decode_package(payload, 4)  
            print(temp_pack, end = "")
        except Exception as decode_err:
            print(f"Decode error for key={seq}: {decode_err}")
        print()

