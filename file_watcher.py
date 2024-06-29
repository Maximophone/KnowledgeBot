import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import traceback

class FileModifiedHandler(FileSystemEventHandler):
    def __init__(self, callback, condition_check, ignore_set=None):
        self.callback = callback
        self.condition_check = condition_check
        self.ignore_set = ignore_set or set()
        super().__init__()

    def on_any_event(self, event):
        print("an event happened!", flush=True)
        print(event, flush=True)

    def on_modified(self, event):
        print("Modified triggered", flush=True)
        if event.is_directory:
            return
        if event.src_path in self.ignore_set:
            self.ignore_set.remove(event.src_path)
            return
        
        if self.condition_check(event.src_path):
            print("And condition triggered", flush=True)
            self.callback(event.src_path)

def poll_for_changes(path, callback, condition_check):
    last_modified_times = {}
    for root, _, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            last_modified_times[file_path] = os.path.getmtime(file_path)

    print("Built index of modified times")
    while True:
        try:
            time.sleep(0.1)  # Check every 0.1 seconds
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    current_mtime = os.path.getmtime(file_path)
                    if file_path in last_modified_times:
                        if current_mtime > last_modified_times[file_path]:
                            print("file modified!", flush=True)
                            if condition_check(file_path):
                                print("condition checked!", flush=True)
                                callback(file_path)
                            last_modified_times[file_path] = current_mtime
                    else:
                        last_modified_times[file_path] = current_mtime
        except Exception:
            print(f"Error in file polling:")
            print(traceback.format_exc())


def start_file_watcher(path, callback, condition_check, ignore_set=None, use_polling=False):
    if use_polling:
        print("Starting file polling.", flush=True)
        poll_for_changes(path, callback, condition_check)
    else:
        event_handler = FileModifiedHandler(callback, condition_check, ignore_set)
        observer = Observer()
        observer.schedule(event_handler, path, recursive=True)
        observer.start()
        print("File watcher started.", flush=True)
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()