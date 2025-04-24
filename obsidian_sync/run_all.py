import subprocess
import sys
import time
import signal
import os

def run_all():
    """Launches main.py and the Streamlit dashboard concurrently."""
    processes = []
    main_script = "main.py"
    dashboard_script = "dashboard.py"

    # Command to run the sync script
    sync_cmd = [sys.executable, main_script]
    # Command to run the streamlit dashboard
    # Use 'streamlit.cmd' on Windows if 'streamlit' isn't directly found
    streamlit_executable = "streamlit.cmd" if os.name == 'nt' else "streamlit"
    dashboard_cmd = [streamlit_executable, "run", dashboard_script]

    print(f"Starting sync script: {' '.join(sync_cmd)}")
    # Start main.py
    # Use CREATE_NEW_PROCESS_GROUP on Windows for better Ctrl+C handling
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    sync_proc = subprocess.Popen(sync_cmd, creationflags=creationflags)
    processes.append(sync_proc)
    print(f"Sync script started (PID: {sync_proc.pid})")

    # Small delay before starting dashboard, purely cosmetic
    time.sleep(2)

    print(f"Starting dashboard: {' '.join(dashboard_cmd)}")
    # Start dashboard.py
    dashboard_proc = subprocess.Popen(dashboard_cmd, creationflags=creationflags)
    processes.append(dashboard_proc)
    print(f"Dashboard started (PID: {dashboard_proc.pid})")
    print("Both processes are running. Press Ctrl+C to stop.")

    try:
        # Wait for processes to complete (they won't, normally)
        # This loop keeps the main script alive until Ctrl+C
        while True:
            for proc in processes:
                retcode = proc.poll()
                if retcode is not None: # Process finished unexpectedly
                    print(f"Process {proc.pid} exited with code {retcode}. Stopping all...")
                    raise KeyboardInterrupt # Trigger cleanup
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nCtrl+C received. Terminating processes...")
        for proc in processes:
            try:
                if proc.poll() is None: # If process is still running
                    print(f"Terminating process {proc.pid}...")
                    if os.name == 'nt':
                        # Send Ctrl+C event on Windows
                        proc.send_signal(signal.CTRL_C_EVENT)
                        try:
                            proc.wait(timeout=5) # Wait a bit for graceful shutdown
                        except subprocess.TimeoutExpired:
                            print(f"Process {proc.pid} did not terminate gracefully, killing...")
                            proc.terminate() # Force terminate if needed
                            proc.wait(timeout=2)
                    else:
                        # Send SIGTERM on Unix-like systems
                        proc.terminate()
                        try:
                             proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            print(f"Process {proc.pid} did not terminate gracefully, killing...")
                            proc.kill() # Force kill if SIGTERM failed
                            proc.wait(timeout=2)
                    print(f"Process {proc.pid} terminated.")
            except ProcessLookupError:
                 print(f"Process {proc.pid} already terminated.")
            except Exception as e:
                 print(f"Error terminating process {proc.pid}: {e}")
        print("All processes stopped.")
    except Exception as e:
         print(f"An unexpected error occurred in run_all: {e}")

if __name__ == "__main__":
    run_all() 