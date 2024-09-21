import os
def ensure_directory_exists(file_path):
    # Extract the directory path from the file path
    directory = os.path.dirname(file_path)
    
    # Create the directory if it does not exist
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

