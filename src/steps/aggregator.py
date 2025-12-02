import json
import sys
import os
import shutil
import time
from pathlib import Path
from typing import Dict, Any, List

# --- START PATH FIX FOR ISOLATED TESTING ---
# This ensures that when running 'python -m src.steps.aggregator',
# the imports from src.core will work.
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
sys.path.append(str(project_root))
# --- END PATH FIX ---

from src.core.interfaces import PipelineStep
from src.core.config_loader import config


class AggregatorStep(PipelineStep):
    """
    Step 3: Aggregates all individual email analysis files (*.gemini.json)
    into a single, deduplicated master JSON file (data.json).
    """

    def run(self, context: Dict[str, Any] = None):
        print("\n--- Step 3: Aggregating Links ---")

        input_dir = Path(config.get('paths.input_dir'))
        base_dir = Path(config.get('paths.base_dir'))
        output_path = base_dir / config.get('files.raw_data')

        base_dir.mkdir(parents=True, exist_ok=True)

        if not input_dir.is_dir():
            print(f"❌ Error: Input directory '{input_dir}' not found. Run Ingest and Process steps first.")
            return

        # 1. Find all analysis files (*.gemini.json)
        analysis_files = list(input_dir.glob("*.gemini.json"))
        if not analysis_files:
            print(f"⚠️ No .gemini.json files found in {input_dir}. Skipping aggregation.")
            return

        print(f"Found {len(analysis_files)} analysis files to aggregate...")
        master_list = []

        # 2. Process each file
        for analysis_path in analysis_files:
            try:
                # Get the corresponding metadata file (*.json)
                meta_filename = analysis_path.name.replace('.gemini.json', '.json')
                meta_path = analysis_path.with_name(meta_filename)

                if not meta_path.exists():
                    print(f"  -> Skipping {analysis_path.name}: Metadata file missing.")
                    continue

                # Load files
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                with open(analysis_path, 'r', encoding='utf-8') as f:
                    analysis = json.load(f)

                analyzed_links: List[Dict] = analysis.get('analyzed_data', [])

                # Extract specific email metadata
                email_id = meta.get('id')
                date_sent = meta.get('internalDate')  # Unix timestamp

                # 3. Merge data
                for link_entry in analyzed_links:
                    item = link_entry.copy()
                    # Add email context to the link record
                    item['email_id'] = email_id
                    item['date_sent'] = date_sent
                    master_list.append(item)

            except Exception as e:
                print(f"  -> Error processing {analysis_path.name}: {e}")

        # 4. Deduplicate based on URL (first seen wins)
        unique_links = {}
        for item in master_list:
            url = item.get('url')
            # The original logic (first seen wins):
            if url and url not in unique_links:
                unique_links[url] = item

        final_list = list(unique_links.values())

        # 5. Save the final aggregate file
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(final_list, f, indent=4)
            print(f"✅ Aggregation complete. Saved {len(final_list)} unique items to '{output_path}'")
        except Exception as e:
            print(f"❌ Error saving aggregate file: {e}")


# --- TEST BLOCK ---
def _create_mock_files(base_path):
    """Creates dummy input files for testing aggregation."""
    mock_input_dir = base_path / "mock_emails"
    mock_input_dir.mkdir(parents=True, exist_ok=True)

    # Clean up previous mock data if exists
    for f in mock_input_dir.glob("*"):
        os.remove(f)

    print(f"Creating mock input files in: {mock_input_dir}")

    # Email 1: Has Link A and Link B
    with open(mock_input_dir / "email1.json", 'w') as f:
        json.dump({"id": "email1", "internalDate": 1678886400000}, f)
    with open(mock_input_dir / "email1.gemini.json", 'w') as f:
        json.dump({
            "analyzed_data": [
                {"url": "http://linkA.com/test", "analysis": {"title": "A from E1"}},
                {"url": "http://linkB.com/news", "analysis": {"title": "B from E1"}}
            ]
        }, f)

    # Email 2: Has Link A (duplicate) and Link C
    with open(mock_input_dir / "email2.json", 'w') as f:
        json.dump({"id": "email2", "internalDate": 1708886400000}, f)  # Newer date
    with open(mock_input_dir / "email2.gemini.json", 'w') as f:
        json.dump({
            "analyzed_data": [
                {"url": "http://linkA.com/test", "analysis": {"title": "A from E2"}},  # Duplicate URL
                {"url": "http://linkC.com/blog", "analysis": {"title": "C from E2"}}
            ]
        }, f)

    return mock_input_dir


if __name__ == "__main__":
    print("\n--- Testing Aggregator Step ---")

    # 1. Setup mock directories and config override
    mock_base_dir = Path("./temp_aggregator_test")
    mock_base_dir.mkdir(exist_ok=True)

    # Override the config paths for the test run
    # NOTE: This temporary override only works because config_loader is a singleton
    original_input_dir = config._config.get('paths', {}).get('input_dir')
    original_base_dir = config._config.get('paths', {}).get('base_dir')

    config._config['paths']['input_dir'] = str(mock_base_dir / "mock_emails")
    config._config['paths']['base_dir'] = str(mock_base_dir)

    mock_input_dir = _create_mock_files(mock_base_dir)

    try:
        aggregator = AggregatorStep()
        print("Running Aggregation on mock data...")
        aggregator.run()

        # 2. Verification
        output_file = mock_base_dir / config.get('files.raw_data')
        if output_file.exists():
            with open(output_file, 'r') as f:
                data = json.load(f)

            print(f"✅ Success: Output file created with {len(data)} unique items.")
            # We expect 3 unique links: A, B, C. Link A should be from Email 1 (first seen wins).
            assert len(data) == 3, "Expected 3 unique links"
            print("Cleanup...")
        else:
            print("❌ Failure: Output file not created.")

    except Exception as e:
        print(f"❌ Test Failed due to unexpected error: {e}")

    finally:
        # 3. Cleanup
        if mock_base_dir.exists():
            shutil.rmtree(mock_base_dir)

        # 4. Restore original config paths
        if original_input_dir:
            config._config['paths']['input_dir'] = original_input_dir
        if original_base_dir:
            config._config['paths']['base_dir'] = original_base_dir
