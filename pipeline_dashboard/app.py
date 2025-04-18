from flask import Flask, render_template, jsonify, request
import logging
import sys
from pathlib import Path
import asyncio # Import asyncio

# Ensure the status_manager can find project root modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import status manager functions and config/utils needed for instantiation
from pipeline_dashboard.status_manager import (
    load_status_index,
    update_status_index,
    NOTES_DIR # Import NOTES_DIR to display it
)
try:
    from kb_service import instantiate_all_processors
    from integrations.discord import DiscordIOCore
    from config.secrets import DISCORD_BOT_TOKEN # Needed for DiscordIOCore
except ImportError as e:
    print(f"Error importing necessary modules from main project: {e}")
    print("Ensure kb_service.py, integrations.discord, and config.secrets are accessible.")
    sys.exit(1)


app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger('werkzeug')
log.setLevel(logging.INFO) # Keep Flask's default logging level

# --- Initialize shared resources needed by instantiate_all_processors ---
# We only need a subset for reset, but initializing all might be simplest for now
# Consider lazy loading or conditional init if resource usage is high.
# NOTE: This means the dashboard server starts the Discord bot too.
# If this is undesirable, instantiate_all_processors needs refinement.
try:
    logging.info("Initializing DiscordIOCore for processor instantiation...")
    # This will start the bot connection when called by instantiate_all_processors
    # We don't store the task here, as we only need the instance briefly
    discord_io_for_reset = DiscordIOCore(token=DISCORD_BOT_TOKEN)
    # Instantiate processors once at startup? Or per request?
    # Per request is safer for state but less efficient.
    # Let's try per request for now.
except Exception as e:
    logging.error(f"Failed to initialize DiscordIOCore: {e}", exc_info=True)
    # Should the app fail to start?
    # For now, allow starting, but reset for Discord-dependent processors will fail.
    discord_io_for_reset = None


@app.route('/')
def index():
    """Serve the main dashboard page."""
    # Optionally pass the notes directory path to the template
    return render_template('index.html', notes_directory=str(NOTES_DIR))

@app.route('/api/status')
def get_status():
    """Return the current processing status from the index file."""
    status_data = load_status_index()
    return jsonify(status_data)

@app.route('/api/refresh-status', methods=['POST'])
def refresh_status():
    """Trigger a manual refresh of the status index."""
    logging.info("Received request to refresh status index.")
    try:
        new, updated, deleted = update_status_index()
        return jsonify({
            "message": f"Index refreshed successfully. New: {new}, Updated: {updated}, Deleted: {deleted}.",
            "new_files": new,
            "updated_files": updated,
            "deleted_files": deleted
        }), 200
    except Exception as e:
        logging.error(f"Error during status index refresh: {e}", exc_info=True)
        return jsonify({"error": f"Failed to refresh status index: {e}"}), 500

@app.route('/api/reset-stage', methods=['POST'])
async def reset_stage(): # Make the route async
    """Reset a specific processing stage for a file."""
    data = request.get_json()
    if not data or 'filename' not in data or 'stage_name' not in data:
        return jsonify({"error": "Missing filename or stage_name in request"}), 400

    filename = data['filename']
    stage_name = data['stage_name']
    logging.info(f"Received request to reset stage '{stage_name}' for file '{filename}'.")

    if not discord_io_for_reset:
         # Check if Discord was initialized successfully earlier
         # This check might be too simplistic if only *some* resets need discord
         logging.error("DiscordIOCore not available for reset operation.")
         return jsonify({"error": "Server configuration error: Discord not available"}), 500

    try:
        # Instantiate processors *on demand* for this request
        logging.debug(f"Instantiating processors to find '{stage_name}'")
        all_processors = instantiate_all_processors(discord_io_for_reset)

        processor_instance = all_processors.get(stage_name)

        if not processor_instance:
            logging.error(f"No processor found for stage name: '{stage_name}'")
            return jsonify({"error": f"Processor not found for stage '{stage_name}'"}), 404

        if not hasattr(processor_instance, 'reset') or not callable(processor_instance.reset):
            logging.error(f"Processor for stage '{stage_name}' ({processor_instance.__class__.__name__}) does not have a callable 'reset' method.")
            return jsonify({"error": f"Reset not supported for stage '{stage_name}'"}), 400

        # Call the processor's reset method
        logging.debug(f"Calling reset method for {stage_name} on {filename}")
        await processor_instance.reset(filename)

        # Note: The reset method handles file updates internally.
        # The index update happens separately via manual refresh or scheduled task.
        # We could trigger an index update for just this file here, but let's keep it simple.

        logging.info(f"Successfully called reset for stage '{stage_name}' on {filename}")
        return jsonify({"message": f"Reset triggered successfully for stage '{stage_name}' on {filename}. Refresh index to see changes."}), 200

    except Exception as e:
        logging.error(f"Error resetting stage '{stage_name}' for {filename}: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error while resetting stage: {e}"}), 500

if __name__ == '__main__':
    # Run the initial index update when starting the server directly
    print("Performing initial status index update...")
    update_status_index()
    print("Starting Flask server...")
    # Flask's default dev server doesn't directly support async routes well with `app.run`.
    # For proper async handling, use an ASGI server like hypercorn or uvicorn.
    # Example using hypercorn:
    # pip install hypercorn
    # hypercorn pipeline_dashboard.app:app --bind 127.0.0.1:5002
    # For simplicity in development, we *can* run with debug=True, but it's not ideal for async.
    app.run(debug=True, port=5002) 