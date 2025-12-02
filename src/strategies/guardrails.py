from typing import Dict, Any
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.core.interfaces import ContentGuardrail


class PiiGuardrail(ContentGuardrail):
    def check(self, content: str) -> bool:
        # Simple example PII check
        if "SSN:" in content or "Social Security Number" in content:
            print("    [Guardrail] 🛑 PII Detected.")
            return False
        return True


class BrokenLinkGuardrail(ContentGuardrail):
    def check(self, content: str) -> bool:
        if not content: return False
        if "404 Not Found" in content:
            print("    [Guardrail] 🛑 404 Detected.")
            return False
        return True


# --- TEST BLOCK ---
if __name__ == "__main__":
    print("\n--- Testing Guardrails ---")

    pii_checker = PiiGuardrail()
    safe_text = "Hello world, this is a public article."
    unsafe_text = "My Social Security Number is 123-45..."

    print(f"Checking Safe Text: {'✅ Passed' if pii_checker.check(safe_text) else '❌ Failed'}")
    print(
        f"Checking Unsafe Text: {'❌ Failed (Expected)' if not pii_checker.check(unsafe_text) else '✅ Passed (Unexpected)'}")
