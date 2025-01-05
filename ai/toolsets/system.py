import os
import subprocess
from ..tools import tool
import shutil

@tool(
    description="Save a file to disk. Can optionally overwrite existing files, but this should be used with extreme caution.",
    path="The file path",
    content="The content to write",
    overwrite="Whether to allow overwriting existing files (defaults to False). Use with extreme caution!",
    safe=False  # This modifies the file system
)
def save_file(path: str, content: str, overwrite: bool = False) -> str:
    try:
        # Check if file already exists
        if os.path.exists(path) and not overwrite:
            return f"Error: File {path} already exists. Cannot overwrite existing files unless overwrite=True."
            
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Write the content to the file
        with open(path, 'w', encoding='utf-8') as file:
            file.write(content)
            
        return f"File saved to {path}"
    except Exception as e:
        return f"Error saving file: {str(e)}"

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

@tool(
    description="Execute Python code. WARNING: This tool can be dangerous as it executes arbitrary Python code. Use with extreme caution.",
    code="The Python code to execute",
    safe=False  # This is definitely not safe
)
def execute_python(code: str) -> str:
    """Executes Python code and returns the output"""
    import io
    import sys
    from contextlib import redirect_stdout, redirect_stderr

    try:
        # Create string buffers to capture output
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        
        # Create a new dictionary for local variables
        local_vars = {}
        
        # Execute the code while capturing both stdout and stderr
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exec(code, {}, local_vars)
        
        # Collect output
        output = stdout_buffer.getvalue()
        errors = stderr_buffer.getvalue()
            
        # Combine stdout and stderr if there are any
        if errors:
            output += f"\nErrors:\n{errors}"
            
        return output if output else "Code executed successfully with no output"
        
    except Exception as e:
        return f"Error executing Python code: {str(e)}"

@tool(
    description="Copy or move a file from source to destination. By default, copies the file; can move (delete original) if specified. Can optionally overwrite existing destination files, but this should be used with extreme caution.",
    source="The source file path",
    destination="The destination file path",
    move="Whether to move the file instead of copying (defaults to False)",
    overwrite="Whether to allow overwriting existing destination files (defaults to False). Use with extreme caution!",
    safe=False  # This modifies the file system
)
def copy_file(source: str, destination: str, move: bool = False, overwrite: bool = False) -> str:
    try:
        # Check if source exists
        if not os.path.exists(source):
            return f"Error: Source file {source} does not exist."
            
        # Check if destination already exists
        if os.path.exists(destination) and not overwrite:
            return f"Error: Destination file {destination} already exists. Cannot overwrite existing files unless overwrite=True."
            
        # Create destination directories if they don't exist
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        
        # Perform the copy or move operation
        if move:
            shutil.move(source, destination)
            return f"File moved from {source} to {destination}"
        else:
            shutil.copy2(source, destination)  # copy2 preserves metadata
            return f"File copied from {source} to {destination}"
            
    except Exception as e:
        return f"Error copying/moving file: {str(e)}"

# Export the tools in this toolset
TOOLS = [save_file, run_command, read_file, list_directory, execute_python, copy_file] 