import os
import subprocess
import threading
import time
import uuid
from ai_core.tools import tool
import shutil
import requests
from integrations.html_to_markdown import HTMLToMarkdown

# Global mapping of session IDs to shell processes
_shell_sessions = {}
_session_last_activity = {}
_shell_lock = threading.Lock()

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
    description="Read the contents of a file (limited to first 100,000 characters)",
    path="The file path",
    safe=True
)
def read_file(path: str) -> str:
    CHAR_LIMIT = 20_000  # About the size of a small book
    with open(path, 'r', encoding='utf-8') as file:
        content = file.read(CHAR_LIMIT)
        if len(content) == CHAR_LIMIT:
            content += "\n... (file truncated due to length)"
    return content

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

@tool(
    description="Fetch content from a webpage and convert it to markdown or return raw HTML",
    url="The URL to fetch content from",
    raw_html="Whether to return the raw HTML instead of converting to markdown (defaults to False)",
    safe=True
)
def fetch_webpage(url: str, raw_html: bool = False) -> str:
    """Fetches content from a URL and returns it as markdown or raw HTML"""
    try:
        if raw_html:
            # Make the request to get the webpage content
            response = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            })
            response.raise_for_status()
            return response.text
            
        # Convert to markdown using the HTMLToMarkdown integration
        converter = HTMLToMarkdown()
        return converter.convert_url(url)
        
    except Exception as e:
        return f"Error fetching webpage: {str(e)}"

@tool(
    description="Run a command in a persistent shell session that maintains state between calls. Returns a session_id when first called. For subsequent commands, provide the same session_id to maintain shell state (directory, environment variables, etc.).",
    command="The command to run",
    session_id="Session ID for an existing shell (leave empty to create a new session)",
    timeout="Timeout in seconds (default: 30)",
    safe=False
)
def persistent_shell(command: str, session_id: str = "", timeout: int = 30) -> str:
    """
    Runs a command in a persistent shell session that maintains state between calls.
    
    If session_id is empty, creates a new shell session and returns the session ID.
    For subsequent calls, provide the same session_id to maintain state.
    """
    global _shell_sessions, _session_last_activity
    
    with _shell_lock:
        # Create a new session if no session ID provided
        is_new_session = not session_id
        if is_new_session:
            session_id = str(uuid.uuid4())
            
            # For Windows
            startup_info = None
            if os.name == 'nt':
                shell_command = ['cmd.exe', '/q']
            else:  # Unix/Linux
                shell_command = ['bash', '--login']
                
            process = subprocess.Popen(
                shell_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                startupinfo=startup_info
            )
            
            _shell_sessions[session_id] = process
            _session_last_activity[session_id] = time.time()
            
            # If no command was provided, just return the session info
            if not command or command.strip() == "":
                return f"Created new shell session with ID: {session_id}\n\nUse this ID for subsequent commands to maintain shell state."
            
            # Otherwise continue to execute the command
        else:
            # Check if the session exists
            if session_id not in _shell_sessions:
                return f"Error: Session {session_id} not found or has expired. Please create a new session."
            
            process = _shell_sessions[session_id]
            
            # Check if process is still alive
            if process.poll() is not None:
                del _shell_sessions[session_id]
                return f"Error: Shell process has exited. Please create a new session."
        
        try:
            # Update last activity time
            _session_last_activity[session_id] = time.time()
            
            # Create a command file that outputs the result to a temporary file
            # This avoids issues with reading from pipes
            temp_dir = os.environ.get('TEMP', '/tmp') if os.name == 'nt' else '/tmp'
            output_file = os.path.join(temp_dir, f"shell_output_{session_id}.txt")
            done_file = os.path.join(temp_dir, f"shell_output_{session_id}.done")
            
            # Clear any previous output file
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except:
                    pass
            if os.path.exists(done_file):
                try:
                    os.remove(done_file)
                except:
                    pass
            
            if os.name == 'nt':  # Windows
                full_command = f"{command} > \"{output_file}\" 2>&1 & echo Done > \"{done_file}\"\n"
            else:  # Unix
                full_command = f"{command} > \"{output_file}\" 2>&1; echo Done > \"{done_file}\"\n"
            
            # Send command to the shell
            process.stdin.write(full_command)
            process.stdin.flush()
            
            # Wait for command to complete with timeout
            start_time = time.time()
            output = ""
            
            while time.time() - start_time < timeout:
                # Check for done file
                if os.path.exists(done_file):
                    break
                
                # Check if process died
                if process.poll() is not None:
                    if session_id in _shell_sessions:
                        del _shell_sessions[session_id]
                    return f"Error: Shell process exited unexpectedly. Please create a new session."
                
                time.sleep(0.1)
            
            # Read the output file
            if os.path.exists(output_file):
                try:
                    with open(output_file, 'r', encoding='utf-8', errors='replace') as f:
                        output = f.read()
                except Exception as e:
                    output = f"Error reading output file: {str(e)}"
            
            # Clean up temporary files
            try:
                if os.path.exists(output_file):
                    os.remove(output_file)
                if os.path.exists(done_file):
                    os.remove(done_file)
            except:
                pass  # Ignore cleanup errors
            
            # If we've timed out
            if time.time() - start_time >= timeout:
                output += "\n[Command timed out after {} seconds]".format(timeout)
            
            # Update activity time again
            _session_last_activity[session_id] = time.time()
            
            # Clean up old sessions
            _cleanup_old_sessions()
            
            # For new sessions, include the session ID in the result
            if is_new_session:
                prefix = f"Created new shell session with ID: {session_id}\n\n"
                return f"{prefix}{output.strip() if output else f'{prefix}Command completed with no output'}"
            else:
                return output.strip() if output else "Command completed with no output"
            
        except Exception as e:
            # If process had an error, clean it up
            if session_id in _shell_sessions:
                try:
                    _shell_sessions[session_id].terminate()
                except:
                    pass
                del _shell_sessions[session_id]
                if session_id in _session_last_activity:
                    del _session_last_activity[session_id]
            
            return f"Error executing command: {str(e)}"

def _read_until_prompt(process, timeout):
    """
    This function is no longer used in the file-based implementation.
    Kept for backward compatibility.
    """
    return ""

def _cleanup_old_sessions():
    """Cleans up sessions that have been idle for more than 1 hour"""
    current_time = time.time()
    idle_limit = 3600  # 1 hour in seconds
    
    for session_id in list(_session_last_activity.keys()):
        if current_time - _session_last_activity[session_id] > idle_limit:
            if session_id in _shell_sessions:
                try:
                    _shell_sessions[session_id].terminate()
                except:
                    pass
                del _shell_sessions[session_id]
            del _session_last_activity[session_id]

# Export the tools in this toolset
TOOLS = [save_file, run_command, read_file, list_directory, execute_python, copy_file, fetch_webpage, persistent_shell] 