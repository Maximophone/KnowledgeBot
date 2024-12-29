import os
import subprocess
from ..tools import tool

@tool(
    description="Save a file to disk",
    path="The file path",
    content="The content to write",
    safe=False  # This modifies the file system
)
def save_file(path: str, content: str) -> str:
    # Implementation...
    return f"File saved to {path}"

@tool(
    description="Run a command on the system, using subprocess, returns the output of the command. Whenever possible, try and use other tools instead of this one.",
    command="The command to run",
    safe=False
)
def run_command(command: str) -> str:
    """Runs a command on the system, returns the output of the command"""
    try:
        # Use subprocess.run instead of os.system for better security and output capture
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        # Combine stdout and stderr
        output = result.stdout
        if result.stderr:
            output += "\nErrors:\n" + result.stderr
            
        return output if output else "Command completed with no output"
        
    except Exception as e:
        return f"Error executing command: {str(e)}"

@tool(
    description="Read the contents of a file",
    path="The file path",
    safe=True
)
def read_file(path: str) -> str:
    with open(path, 'r') as file:
        return file.read()

@tool(
    description="Lists the contents of a directory",
    path="The directory path",
    safe=True
)
def list_directory(path: str) -> str:
    return os.listdir(path)

# Export the tools in this toolset
TOOLS = [save_file, run_command, read_file, list_directory] 