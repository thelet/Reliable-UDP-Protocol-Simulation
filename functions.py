import sys
from typing import Dict, List
import os

import subprocess


def run_script_in_new_terminal(script_path):
    """
    Runs a Python script in a new terminal window.

    Args:
        script_path (str): The path to the Python script to run.
    """
    try:
        # Adjust command based on your OS
        command = [
            "python",  # Use 'python3' if needed
            script_path,
        ]

        # On Windows: Use `start` to open in a new terminal
        subprocess.Popen(["start", "cmd", "/k"] + command, shell=True)

        # On macOS/Linux: Use `gnome-terminal`, `xterm`, or equivalent
        # subprocess.Popen(["gnome-terminal", "--"] + command)

        print(f"Running {script_path} in a new terminal window.")
    except Exception as e:
        print(f"Error running script {script_path}: {e}")


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




def get_from_file(file_path : str):
        try:
            with open(file_path, 'r') as file:
                data = file.readlines()
                params = {}
                for line in data:
                    params[line.split(":")[0].strip("\n")] = line.split(":")[1].strip("\n")
            return params
        except Exception as e:
            print(f"Unvalid parameters from file: {e}")



def validate_input(params : Dict[str, str]) -> None:
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
            file_path = os.path.join(current_directory, file_name)

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
    try:
        with open(filename, "w") as file:
            for key, value in params.items():
                file.write(f"{key}:{value}\n")
    except Exception as e:
        print(f"Error while writing to file: {e}")
