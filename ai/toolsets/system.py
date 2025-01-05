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

# Export the tools in this toolset
TOOLS = [save_file, run_command, read_file, list_directory, execute_python] 