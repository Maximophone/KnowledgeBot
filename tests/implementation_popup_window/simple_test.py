import os
import sys
import traceback

try:
    print("Beginning test")
    
    # Check if the ui module exists
    print(f"Checking for UI module...")
    import ui
    print(f"UI module found: {ui}")
    
    # Check if the popup_window module exists
    print(f"Checking for popup_window module...")
    import ui.popup_window
    print(f"Popup window module found: {ui.popup_window}")
    
    # Check prompt loading function
    print(f"Testing load_prompts function...")
    from ui.popup_window import load_prompts
    
    # Check if the prompts directory exists
    from config.paths import PATHS
    print(f"Prompts directory path: {PATHS.prompts_library}")
    print(f"Prompts directory exists: {os.path.exists(PATHS.prompts_library)}")
    
    # Try loading prompts
    if os.path.exists(PATHS.prompts_library):
        prompts = load_prompts(PATHS.prompts_library)
        print(f"Loaded {len(prompts)} prompts")
        if prompts:
            print(f"Sample prompt keys: {list(prompts.keys())[:3]}")
    
    print("Test completed successfully")
except Exception as e:
    print(f"Error: {e}")
    print(traceback.format_exc()) 