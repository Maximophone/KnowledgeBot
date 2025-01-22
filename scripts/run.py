"""Script runner utility to discover and run available scripts."""

import importlib
import inspect
import pkgutil
import sys
from pathlib import Path
import scripts
from scripts.base_script import BaseScript
import argparse
import logging
from config.logging_config import setup_logger

logger = setup_logger(__name__)

def discover_scripts():
    """Discover all available scripts in the scripts directory."""
    scripts_dir = Path(__file__).parent
    script_classes = {}
    
    # Walk through all python files in the scripts directory
    for (_, name, _) in pkgutil.iter_modules([str(scripts_dir)]):
        if name == 'base_script' or name == 'run':
            continue
            
        try:
            # Import the module
            module = importlib.import_module(f"scripts.{name}")
            
            # Find all classes that inherit from BaseScript
            for item_name, item in inspect.getmembers(module):
                if (inspect.isclass(item) and 
                    issubclass(item, BaseScript) and 
                    item != BaseScript):
                    script_instance = item()
                    script_classes[script_instance.name] = script_instance
        except Exception as e:
            logger.error(f"Failed to load script {name}: {e}")
    
    return script_classes

def list_available_scripts(scripts_dict):
    """Print available scripts and their descriptions."""
    print("\nAvailable scripts:")
    print("-" * 50)
    for name, script in scripts_dict.items():
        print(f"{name}: {script.description}")
    print()

def main():
    parser = argparse.ArgumentParser(description="Run knowledge bot scripts")
    parser.add_argument('script_name', nargs='?', help='Name of the script to run')
    parser.add_argument('--list', '-l', action='store_true', help='List available scripts')
    parser.add_argument('args', nargs=argparse.REMAINDER, help='Arguments to pass to the script')
    
    args = parser.parse_args()
    available_scripts = discover_scripts()
    
    if args.list or not args.script_name:
        list_available_scripts(available_scripts)
        return
    
    if args.script_name not in available_scripts:
        print(f"Error: Script '{args.script_name}' not found")
        list_available_scripts(available_scripts)
        return
    
    script = available_scripts[args.script_name]
    logger.info(f"Running script: {args.script_name}")
    script.run(*args.args)

if __name__ == "__main__":
    main() 