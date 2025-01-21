import json
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import traceback
import asyncio
from typing import Set, Dict
from config.logging_config import setup_logger
from pathlib import Path

logger = setup_logger(__name__)

class FileModifiedHandler(FileSystemEventHandler):
    def __init__(self, callback, condition_check, ignore_set=None):
        self.callback = callback
        self.condition_check = condition_check
        self.ignore_set = ignore_set or set()
        self.logger = setup_logger(f"{__name__}.FileModifiedHandler")
        super().__init__()

    def on_any_event(self, event):
        self.logger.debug("Event detected: %s", event)

    def on_modified(self, event):
        self.logger.debug("Modified event triggered")
        if event.is_directory:
            return
        if event.src_path in self.ignore_set:
            self.ignore_set.remove(event.src_path)
            return
        
        if self.condition_check(event.src_path):
            self.logger.debug("Condition triggered for file: %s", event.src_path)
            self.callback(event.src_path)

async def poll_for_changes(path, callback, condition_check):
    last_modified_times = {}
    for root, _, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            if ".smart-connections" in file_path:
                continue
            last_modified_times[file_path] = os.path.getmtime(file_path)

    logger.info("Built index of modified times")
    while True:
        try:
            await asyncio.sleep(0.1)  # Check every 0.1 seconds
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if ".smart-connections" in file_path:
                        continue
                    current_mtime = os.path.getmtime(file_path)
                    if file_path in last_modified_times:
                        if current_mtime > last_modified_times[file_path]:
                            logger.debug("File modified: %s", file_path)
                            try:
                                if condition_check(file_path):
                                    logger.debug("Condition check passed for file: %s", file_path)
                                    callback(file_path)
                                last_modified_times[file_path] = current_mtime
                            except Exception:
                                logger.error("Error when checking condition for file %s", file_path)
                                logger.error(traceback.format_exc())
                    else:
                        last_modified_times[file_path] = current_mtime
        except Exception:
            logger.error("Error in file polling:")
            logger.error(traceback.format_exc())

class ObsidianWorkspaceWatcher:
    def __init__(self, vault_path: str, callback, condition_check):
        self.vault_path = vault_path
        self.workspace_file = os.path.join(vault_path, '.obsidian', 'workspace.json')
        self.callback = callback
        self.condition_check = condition_check
        self.open_files: Set[str] = set()
        self.last_modified_times: Dict[str, float] = {}
        self.last_loop_time = time.time()
        self.logger = setup_logger(f"{__name__}.ObsidianWorkspaceWatcher")

    def _get_open_files(self) -> Set[str]:
        """Extract all open file paths from workspace.json"""
        try:
            with open(self.workspace_file, 'r', encoding='utf-8') as f:
                workspace = json.load(f)
                
            open_files = set()
            # Look for files in the main tabs
            if 'main' in workspace and 'children' in workspace['main']:
                for child in workspace['main']['children']:
                    if 'children' in child:
                        for tab in child['children']:
                            if ('state' in tab and 'state' in tab['state'] 
                                and 'file' in tab['state']['state']):
                                # Use Path to handle file paths in a platform-independent way
                                file_path = Path(self.vault_path) / tab['state']['state']['file']
                                file_path = str(file_path.resolve())  # Normalize the path
                                open_files.add(file_path)
            return open_files
            
        except Exception as e:
            self.logger.error("Error reading workspace file: %s", e)
            return set()

    async def start_watching(self):
        self.logger.info("Starting workspace watcher")
        while True:
            try:
                current_time = time.time()
                loop_delay = current_time - self.last_loop_time
                self.logger.debug(f"Loop delay: {loop_delay*1000:.2f}ms")
                self.last_loop_time = current_time

                # Update list of files to watch
                current_open_files = self._get_open_files()
                
                # Check each open file for modifications
                for file_path in current_open_files:
                    # print(f"Checking file {file_path}", flush=True)
                    try:
                        # Normalize the file path before checking
                        normalized_path = str(Path(file_path).resolve())
                        current_mtime = os.path.getmtime(normalized_path)
                        last_mtime = self.last_modified_times.get(normalized_path, 0)
                        
                        if current_mtime > last_mtime:
                            self.logger.debug("File %s modified", normalized_path)
                            if self.condition_check(normalized_path):
                                self.logger.debug("Condition checked for file %s", normalized_path)
                                self.callback(normalized_path)
                            self.last_modified_times[normalized_path] = current_mtime
                            
                    except OSError:
                        # Handle case where file might have been deleted
                        if file_path in self.last_modified_times:
                            del self.last_modified_times[file_path]
                
                # Clean up last_modified_times for closed files
                self.last_modified_times = {
                    f: t for f, t in self.last_modified_times.items() 
                    if f in current_open_files
                }
                
                # We can poll much more frequently now since we're checking fewer files
                await asyncio.sleep(0.1)  # 100ms polling interval
                
            except Exception as e:
                self.logger.error(f"Error in workspace watcher: {e}")
                await asyncio.sleep(1)  # Longer sleep on error


async def start_file_watcher(path, callback, condition_check, ignore_set=None, use_polling=False):
    if use_polling:
        logger.info("Starting file watcher in polling mode")
        watcher = ObsidianWorkspaceWatcher(path, callback, condition_check)
        await watcher.start_watching()
    else:
        logger.info("Starting file watcher in event mode")
        event_handler = FileModifiedHandler(callback, condition_check, ignore_set)
        observer = Observer()
        observer.schedule(event_handler, path, recursive=True)
        observer.start()
        logger.info("File watcher started.")
        
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()