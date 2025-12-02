import yaml
import os
import sys
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ConfigManager:
    _instance = None
    _config: Dict[str, Any] = {}
    _prompts: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_config()
            cls._instance._load_prompts()
        return cls._instance

    def _load_config(self):
        """Loads config.yaml and overrides with Environment Variables if needed."""
        # Search order for config file
        paths = [Path("config/config.yaml"), Path("myndscribe.config.yaml")]
        config_path = next((p for p in paths if p.exists()), None)

        if not config_path:
            print("⚠️ Warning: No config.yaml found. Using defaults.")
            return

        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)

    def _load_prompts(self):
        """Loads prompts from a separate YAML file."""
        prompt_path = Path("config/prompts.yaml")
        if prompt_path.exists():
            with open(prompt_path, 'r', encoding='utf-8') as f:
                self._prompts = yaml.safe_load(f)

    def get(self, path: str, default=None):
        """Access config using dot notation."""
        keys = path.split('.')
        value = self._config
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def get_prompt(self, prompt_name: str) -> str:
        return self._prompts.get(prompt_name, "")

    @property
    def api_key(self):
        return os.getenv("GEMINI_API_KEY")


# Global instance
config = ConfigManager()

# --- TEST BLOCK ---
if __name__ == "__main__":
    print("\n--- Testing Config Loader ---")
    print(f"1. Input Dir: {config.get('paths.input_dir')}")
    print(f"2. API Key Present: {bool(config.api_key)}")
    print(f"3. LinkedIn Enabled: {config.get('strategies.linkedin.enabled')}")

    if not config.get('paths.input_dir'):
        print("❌ Error: Config not loaded correctly (check myndscribe.config.yaml location)")
    else:
        print("✅ Config Loaded Successfully")
