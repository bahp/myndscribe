import sys
from pathlib import Path

# --- START PATH FIX FOR ISOLATED TESTING ---
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
sys.path.append(str(project_root))
# --- END PATH FIX ---

from src.core.interfaces import PipelineStep
from src.core.config_loader import config

class ConverterStep(PipelineStep):
    """
    Step 6: Converts the final processed JSON file into a JavaScript variable
    for use on the frontend webpage.
    """
    def run(self, context=None):
        print("\n--- Step 6: Converting to JavaScript ---")

        base_dir = Path(config.get('paths.base_dir'))
        web_dir = Path(config.get('paths.web_dir'))

        # Input is the processed data (after standardization and link checking)
        input_path = base_dir / config.get('files.processed_data')
        output_path = web_dir / config.get('files.js_output')

        if not input_path.exists():
            print(f"❌ Input file missing: {input_path}")
            return

        try:
            # Ensure output directory exists
            web_dir.mkdir(parents=True, exist_ok=True)

            # Read JSON
            with open(input_path, 'r', encoding='utf-8') as f:
                json_content = f.read()

            # Add JS variable wrapper
            js_content = f"var data = {json_content};"

            # Write JS
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(js_content)

            print(f"✅ Successfully generated JS variable at '{output_path}'")

        except Exception as e:
            print(f"❌ Error converting to JS: {e}")

# --- TEST BLOCK ---
if __name__ == "__main__":
    print("\n--- Testing Converter Step Initialization ---")
    try:
        ConverterStep()
        print("✅ ConverterStep Initialized Successfully.")
    except Exception as e:
        print(f"❌ Initialization Failed: {e}")
