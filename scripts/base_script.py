"""Base class for all runnable scripts in the system."""

from abc import ABC, abstractmethod
import json
from datetime import datetime
from pathlib import Path
import logging
from config.logging_config import setup_logger

logger = setup_logger(__name__)

class BaseScript(ABC):
    def __init__(self):
        self.base_output_dir = Path("data/script_outputs")
        self.base_output_dir.mkdir(parents=True, exist_ok=True)
        # Create script-specific subfolder using the script's name
        self.output_dir = self.base_output_dir / self.name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the script"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Return a description of what the script does"""
        pass
    
    @abstractmethod
    def run(self, **kwargs):
        """Main execution method to be implemented by each script"""
        pass
    
    def save_json_output(self, data: dict, filename: str):
        """Helper method to save script output as JSON"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"{filename}_{timestamp}.json"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved output to {output_path}")
        return output_path 