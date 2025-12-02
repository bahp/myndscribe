import os
import json
import logging
from pathlib import Path

# Configure logging to see which files are being processed and deleted
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def cleanup_login_walls(directory_path='.'):
    """
    Loops through all '*.gemini.json' files in a directory, checks for the
    'Login Wall' tag inside the 'analyzed_data' list, and removes the
    file itself if the tag is found.

    This version uses the pathlib module for cleaner path handling.

    Args:
        directory_path (str): The path to the directory to scan. Defaults to the
                              current directory ('.').
    """

    # Use Path for modern path handling and ensure it's absolute
    base_dir = Path(directory_path).resolve()
    logging.info(f"Starting cleanup in directory: {base_dir}")

    # 1. Iterate ONLY through files that end in 'gemini.json'
    for current_file_path in base_dir.glob('*.gemini.json'):

        filename = current_file_path.name

        logging.info(f"Checking file: {filename}")

        try:
            # 2. Read the content of the JSON file
            with open(current_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 3. Check for the 'Login Wall' tag
            is_login_wall = False

            # Logic: data -> analyzed_data (list) -> item -> analysis (dict) -> tags (list)
            analyzed_data = data.get('analyzed_data')

            if analyzed_data and isinstance(analyzed_data, list):
                for item in analyzed_data:
                    analysis = item.get('analysis')
                    if analysis and isinstance(analysis, dict):
                        tags = analysis.get('tags')

                        if tags and isinstance(tags, list):
                            if 'Login Wall' in tags:
                                is_login_wall = True
                                # If found, no need to check other items in the list
                                break

                                # 4. If the tag is found, remove the current file
            if is_login_wall:
                logging.warning(f"  --> 'Login Wall' tag detected in {filename}. Preparing for deletion.")

                if current_file_path.exists():
                    try:
                        # Use Path.unlink() for deletion
                        current_file_path.unlink()
                        logging.critical(f"    DELETED: {current_file_path.name}")
                    except OSError as e:
                        logging.error(f"    Error removing {current_file_path.name}: {e}")
                else:
                    # Should not happen if glob found it, but good practice
                    logging.debug(f"    Skipped: {current_file_path.name} unexpectedly does not exist.")
            else:
                logging.info(f"  --> Tag not found. Skipping.")

        except json.JSONDecodeError:
            logging.error(f"  Error: Could not decode JSON from {filename}. Skipping.")
        except IOError as e:
            logging.error(f"  Error reading file {filename}: {e}. Skipping.")
        except Exception as e:
            logging.error(f"  An unexpected error occurred with {filename}: {e}. Skipping.")

    logging.info("Cleanup process finished.")


if __name__ == '__main__':
    # You can specify a different path here, e.g., cleanup_login_walls('/path/to/your/data')
    # If no argument is provided, it defaults to the current working directory.
    cleanup_login_walls(directory_path='../outputs/emails/')
