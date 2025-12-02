from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class PipelineStep(ABC):
    """
    Contract for any step in the ETL pipeline.
    """
    @abstractmethod
    def run(self, context: Dict[str, Any] = None):
        """Executes the step logic."""
        pass

class ContentFetcherStrategy(ABC):
    """
    Contract for fetching content from a URL.
    """
    @abstractmethod
    def fetch(self, url: str) -> Optional[str]:
        """Returns the raw text content of the URL or None."""
        pass

class ContentGuardrail(ABC):
    """
    Contract for checking content (PII, Broken Links, etc.).
    """
    @abstractmethod
    def check(self, content: str) -> bool:
        """Return True if content is valid/safe, False otherwise."""
        pass
