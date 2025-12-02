import sys
from pathlib import Path

# --- START PATH FIX FOR ISOLATED TESTING ---
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root))
# --- END PATH FIX ---

from src.core.config_loader import config
from src.steps.email_ingest import EmailIngestStep
from src.steps.smart_processor import SmartProcessorStep
from src.steps.aggregator import AggregatorStep
from src.steps.tag_management import TagManagementStep  # <-- NEW IMPORT
from src.steps.converter import ConverterStep  # <-- NEW IMPORT


class Pipeline:
    def __init__(self):
        # Register available steps here
        self.steps = {
            'ingest': EmailIngestStep(),
            'process': SmartProcessorStep(),
            'aggregate': AggregatorStep(),
            'tags': TagManagementStep(),  # <-- REGISTER TAG STEP
            'convert': ConverterStep(),  # <-- REGISTER CONVERTER STEP (Fixes the error)
        }

    def run(self, target_steps=None):
        if not target_steps:
            target_steps = config.get('pipeline.default_steps')

        print(f"🚀 Starting Pipeline with steps: {target_steps}")

        for step_name in target_steps:
            if step_name in self.steps:
                try:
                    self.steps[step_name].run()
                except Exception as e:
                    print(f"❌ Critical Error in step '{step_name}': {e}")
            else:
                print(f"⚠️ Unknown step requested: {step_name}")


# --- TEST BLOCK ---
if __name__ == "__main__":
    print("\n--- Testing Pipeline Initialization ---")

    # Temporarily ensure all new steps are in the default list for quick testing
    default_steps = config._config.get('pipeline', {}).get('default_steps', [])
    for step in ['tags', 'convert']:
        if step not in default_steps:
            default_steps.append(step)
    config._config['pipeline']['default_steps'] = default_steps

    test_pipeline = Pipeline()

    # Check if the steps are registered
    if all(step in test_pipeline.steps for step in ['aggregate', 'tags', 'convert']):
        print("✅ Pipeline registered 'aggregate', 'tags', and 'convert' steps successfully.")
    else:
        print("❌ Pipeline failed to register all new steps.")
