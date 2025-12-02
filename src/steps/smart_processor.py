import json
import time
import sys
from pathlib import Path
from google import genai

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.core.interfaces import PipelineStep
from src.core.config_loader import config
from src.strategies.fetchers import FetchRouter
from src.strategies.guardrails import PiiGuardrail, BrokenLinkGuardrail


class SmartProcessorStep(PipelineStep):
    def __init__(self):
        # FIX: Removed config argument
        self.router = FetchRouter()

        self.client = None
        if config.api_key:
            self.client = genai.Client(api_key=config.api_key)
        else:
            print("⚠️ Warning: No API Key available for processor.")

        self.model = config.get('strategies.gemini.model_name', "gemini-2.5-flash")

        self.guardrails = [BrokenLinkGuardrail(), PiiGuardrail()]

    def run(self, context=None):
        print("\n--- Step 2: Intelligent Processing ---")
        input_dir = Path(config.get('paths.input_dir'))
        if not input_dir.exists():
            print(f"❌ Input directory {input_dir} not found.")
            return

        files = list(input_dir.glob("*.json"))
        todo = [f for f in files if not f.name.endswith('.gemini.json')
                and not f.with_name(f"{f.stem}.gemini.json").exists()]

        print(f"Found {len(todo)} pending email files.")
        for f in todo:
            self._process_file(f)

    def _process_file(self, file_path: Path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return

        links = data.get('processed_extracted_links', [])
        if not links: return

        analyzed_results = []
        unique_links = sorted(list(set(links)))

        for url in unique_links:
            print(f"  > Processing: {url[:50]}")
            status, content = self.router.get_content(url)

            if not self._run_guardrails(content):
                continue

            if content:
                analysis = self._analyze(content, url)
                if analysis:
                    analyzed_results.append({"url": url, "analysis": analysis})

        # Save results
        output_path = file_path.with_name(f"{file_path.stem}.gemini.json")
        output = {"email_id": file_path.stem, "analyzed_data": analyzed_results}

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=4)
        print(f"    ✅ Saved to {output_path.name}")

    def _run_guardrails(self, content):
        if not content: return False
        for guard in self.guardrails:
            if not guard.check(content): return False
        return True

    def _analyze(self, content, url):
        if not self.client: return None
        template = config.get_prompt("analysis_prompt")
        prompt = template.format(url=url, content=content[:50000])
        try:
            response = self.client.models.generate_content(
                model=self.model, contents=prompt
            )
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            print(f"    [AI Error] {e}")
            return None


# --- TEST BLOCK ---
if __name__ == "__main__":
    print("\n--- Testing Smart Processor ---")
    processor = SmartProcessorStep()

    # Check if we have files to process
    input_dir = Path(config.get('paths.input_dir'))
    if input_dir.exists() and list(input_dir.glob("*.json")):
        print(f"Found files in {input_dir}. Running one pass...")
        # To avoid processing everything in test, we just check init
        print("✅ Processor Initialized. API Client: ", "Ready" if processor.client else "Missing")
    else:
        print(f"⚠️ No input files found in {input_dir}. Run Ingest Step first.")
