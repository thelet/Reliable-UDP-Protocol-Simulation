import sys
from typing import Dict, List, Any
import os




def get_params() -> Dict[str, Any]:
    try:
        paths = find_all_text_files()
        if len(paths) == 1:
            return file_to_json(paths[0])
        if len(paths) >1:
            path = choose_text_file(paths)
            return file_to_json(path)
        if len(paths) == 0:
            print("No text files found")
            params = get_from_user()
            write_dict_to_file(params, "params.txt")
            print("params saved to params.txt")
            return file_to_json("params.txt")
    except Exception as error:
        print(error)



def get_from_user():
        massage = input("Enter a message: ")
        max_msg_size = input("Enter the maximum message size (in bytes): ")
        window_size = input("Enter the window size: ")
        timeout = input("Enter timeout value (in seconds): ")
        params = {
            "massage": massage,
            "maximum_msg_size" :  max_msg_size,
            "window_size" : window_size,
            "timeout" : timeout
        }
        try:
            validate_input(params)
            return params
        except Exception as e:
            print(f"Unvalied parameters from user: {e}")
            sys.exit(1)


def file_to_json(file_path: str) -> dict:
    try:
        json_data = {}

        with open(file_path, 'r') as file:
            for line in file:
                # Skip empty lines or lines without a colon
                if not line.strip() or ':' not in line:
                    continue

                # Split the line into key and value
                key, value = line.strip().split(":", 1)
                key = key.strip()
                value = value.strip()

                # Convert numeric values to integers
                if value.isdigit():
                    value = int(value)

                json_data[key] = value

        return json_data
    except Exception as e:
        raise ValueError(f"Error processing file: {e}")


def validate_input(params : Dict[str, Any]) -> None:
    try:
        for key in params:
            if key == "massage":
                pass
            elif not params[key].isnumeric():
                raise ValueError("all values must be numeric")
            elif int(params[key]) <= 0:
                raise ValueError("all values must be positive")
    except Exception as e:
        print(f"Error while validating parameters: {e}")



def find_all_text_files() -> list[str]:
    try:
        current_directory = os.getcwd()
        text_files = []

        # Iterate over all files in the current directory
        for file_name in os.listdir(current_directory):
            file_path = os.path.join(file_name)

            # Check if it's a .txt file
            if os.path.isfile(file_path) and file_name.endswith('.txt'):
                text_files.append(file_path)

        return text_files
    except Exception as e:
        print(f"Error while searching for text files: {e}")


def choose_text_file(text_files : list[str]) -> str:
    print(f"found more that one text file: {text_files}")
    path_to_params = int(input("Choose a text file: "))
    return text_files[path_to_params]



def slice_json(keys_to_extract):
    json_data = get_params()
    partial_json = {key: json_data[key] for key in keys_to_extract if key in json_data}
    return partial_json

def get_client_params():
    client_keys = ["massage", "timeout", "window_size"]
    return slice_json(client_keys)


def get_server_params():
    server_keys = ["maximum_msg_size"]
    params = slice_json(server_keys)
    params["maximum_msg_size"] = int(params.get("maximum_msg_size", 0))
    if params["maximum_msg_size"] < 4:
        new_value = int(input("maximum_msg_size must be at least 4: enter new max size: "))
        if new_value < 4:
            raise ValueError("maximum_msg_size must be at least 4")
        params["maximum_msg_size"] = new_value
    return params


def write_dict_to_file(params: dict, filename: str) -> None:
    try:
        with open(filename, "w") as file:
            for key, value in params.items():
                file.write(f"{key}:{value}\n")
    except Exception as e:
        print(f"Error while writing to file: {e}")
