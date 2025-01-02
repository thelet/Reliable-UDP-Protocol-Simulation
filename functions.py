from typing import Dict, List
import os

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
        validate_input(params)
        return params


def get_from_file(file_path : str):
        with open(file_path, 'r') as file:
            data = file.readlines()
            params = {}
            for line in data:
                params[line.split(":")[0].strip("\n")] = line.split(":")[1].strip("\n")
        return params



def validate_input(params : Dict[str, str]) -> None:
    for key in params:
        if key == "massage":
            pass
        elif not params[key].isnumeric():
            raise ValueError("all values must be numeric")
        elif int(params[key]) <= 0:
            raise ValueError("all values must be positive")



def find_all_text_files() -> list[str]:
    """
    Find all text files in the current project directory.

    Returns:
        list[str]: A list of absolute paths to all `.txt` files in the current directory.
    """
    current_directory = os.getcwd()
    text_files = []

    # Iterate over all files in the current directory
    for file_name in os.listdir(current_directory):
        file_path = os.path.join(current_directory, file_name)

        # Check if it's a .txt file
        if os.path.isfile(file_path) and file_name.endswith('.txt'):
            text_files.append(file_path)

    return text_files

def choose_text_file(text_files : list[str]) -> str:
    print(f"found more that one text file: {text_files}")
    path_to_params = int(input("Choose a text file: "))
    return text_files[path_to_params]

def get_params() -> Dict[str, str]:
    try:
        paths = find_all_text_files()
        if len(paths) == 1:
            return get_from_file(paths[0])
        if len(paths) >1:
            path = choose_text_file(paths)
            return get_from_file(path)
        if len(paths) == 0:
            print("No text files found")
            params = get_from_user()
            tofile = int(input("enter '1' to save params to file: "))
            if tofile == 1:
                write_dict_to_file(params, "params.txt")
                print("params saved to params.txt")
            return params
    except Exception as error:
        print(error)

def write_dict_to_file(params: dict, filename: str) -> None:
    with open(filename, "w") as file:
        for key, value in params.items():
            file.write(f"{key}:{value}\n")

