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
import traceback

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

def load_items_from_csv(file_path):
    """Load items from a CSV file, expecting one item per row in the first column"""
    try:
        import csv
        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            # Extract first column from each row, skip empty values
            return [row[0].strip() for row in reader if row and row[0].strip()]
    except Exception as e:
        logger.error(f"Failed to load CSV file {file_path}: {e}")
        return None

def load_profile_data_from_csv(file_path: str, id_column: str = None, urn_column: str = None):
    """Load profile data from a CSV file with specified columns for IDs and URNs
    
    Args:
        file_path: Path to the CSV file
        id_column: Name of the column containing profile IDs
        urn_column: Name of the column containing profile URNs
        
    Returns:
        List of dicts with 'profile_id' and 'profile_urn' keys
    """
    try:
        import csv
        
        # Default column names if not specified
        id_column = id_column or 'LinkedIn Profile ID'
        urn_column = urn_column or 'LinkedIn URN ID'
        
        profiles = []
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            # Log found columns
            logger.info(f"Columns found in CSV: {', '.join(reader.fieldnames)}")
            
            # Validate columns exist
            if id_column not in reader.fieldnames and urn_column not in reader.fieldnames:
                raise ValueError(
                    f"Neither '{id_column}' nor '{urn_column}' columns found in CSV. "
                    f"Available columns: {', '.join(reader.fieldnames)}"
                )
            
            # Process each row
            for row in reader:
                profile = {}
                
                # Get profile ID if column exists and value is not empty
                if id_column in reader.fieldnames:
                    value = row[id_column].strip()
                    if value:
                        profile['profile_id'] = value
                
                # Get profile URN if column exists and value is not empty
                if urn_column in reader.fieldnames:
                    value = row[urn_column].strip()
                    if value:
                        profile['profile_urn'] = value
                
                # Only add profiles that have at least one identifier
                if profile:
                    profiles.append(profile)
        
        logger.info(f"Successfully loaded {len(profiles)} profiles from CSV")
        return profiles
        
    except Exception as e:
        logger.error(f"Failed to load profile data from CSV file {file_path}: {str(e)}\n{traceback.format_exc()}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Run knowledge bot scripts")
    parser.add_argument('script_name', nargs='?', help='Name of the script to run')
    parser.add_argument('--list', '-l', action='store_true', help='List available scripts')
    
    # Add script-specific arguments
    parser.add_argument('--action', help='Action to perform (for scripts that support multiple actions)')
    
    # Profile identification arguments - direct lists
    parser.add_argument('--profile-id', help='Profile ID for LinkedIn operations')
    parser.add_argument('--profile-ids', nargs='+', help='List of LinkedIn profile IDs or path to CSV file')
    parser.add_argument('--profile-ids-file', help='Path to CSV file containing LinkedIn profile IDs')
    parser.add_argument('--profile-urn', help='Profile URN for LinkedIn operations')
    parser.add_argument('--profile-urns', nargs='+', help='List of LinkedIn profile URNs or path to CSV file')
    parser.add_argument('--profile-urns-file', help='Path to CSV file containing LinkedIn profile URNs')
    
    # New profile data file arguments
    parser.add_argument('--profile-data-file', help='Path to CSV file containing profile data')
    parser.add_argument('--profile-id-column', help='Name of the column containing profile IDs in the data file')
    parser.add_argument('--profile-urn-column', help='Name of the column containing profile URNs in the data file')
    
    parser.add_argument('--keywords', help='Search keywords')
    
    # Add LinkedIn messenger and bulk email sender specific arguments
    parser.add_argument('--template-file', help='Path to message/email template file')
    parser.add_argument('--contacts-file', help='Path to contacts JSON file for LinkedIn messenger')
    parser.add_argument('--campaign-file', help='Path to campaign markdown file for LinkedIn messenger')
    parser.add_argument('--csv-file', help='Path to CSV file for bulk email sender')
    parser.add_argument('--from-name', help='Display name for the email sender')
    
    args, unknown_args = parser.parse_known_args()
    
    available_scripts = discover_scripts()
    
    if args.list or not args.script_name:
        list_available_scripts(available_scripts)
        return
    
    if args.script_name not in available_scripts:
        print(f"Error: Script '{args.script_name}' not found")
        list_available_scripts(available_scripts)
        return
    
    # Handle profile data loading
    profile_data = None
    if args.profile_data_file:
        profile_data = load_profile_data_from_csv(
            args.profile_data_file,
            args.profile_id_column,
            args.profile_urn_column
        )
        if profile_data is None:
            return
    
    # Handle CSV files for list arguments (legacy support)
    elif args.profile_ids_file:
        args.profile_ids = load_items_from_csv(args.profile_ids_file)
    elif args.profile_ids and len(args.profile_ids) == 1 and args.profile_ids[0].endswith('.csv'):
        args.profile_ids = load_items_from_csv(args.profile_ids[0])
        
    if args.profile_urns_file:
        args.profile_urns = load_items_from_csv(args.profile_urns_file)
    elif args.profile_urns and len(args.profile_urns) == 1 and args.profile_urns[0].endswith('.csv'):
        args.profile_urns = load_items_from_csv(args.profile_urns[0])
    
    script = available_scripts[args.script_name]
    logger.info(f"Running script: {args.script_name}")
    
    # Convert args to dictionary, removing None values and file path arguments
    script_args = {k: v for k, v in vars(args).items() 
                  if v is not None and k not in ['script_name', 'list', 'profile_ids_file', 
                                               'profile_urns_file', 'profile_id_column', 
                                               'profile_urn_column']}
    
    # Add profile_data if available
    if profile_data is not None:
        script_args['profile_data'] = profile_data
    
    script.run(**script_args)

if __name__ == "__main__":
    main() 