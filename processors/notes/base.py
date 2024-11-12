from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import aiofiles
from ..common.frontmatter import parse_frontmatter
import traceback
from ai import AI

class NoteProcessor(ABC):
    """Base class for all note processors in Obsidian vault."""
    
    def __init__(self, input_dir: Path):
        self.input_dir = input_dir
        self.files_in_process = set()
        self.ai_model = AI("sonnet3.5")
        
    @abstractmethod
    def should_process(self, filename: str) -> bool:
        """Determine if a file should be processed."""
        pass
        
    @abstractmethod
    async def process_file(self, filename: str) -> None:
        """Process a single file."""
        pass

    async def read_file(self, filename: str) -> str:
        """Helper method to read file content."""
        async with aiofiles.open(self.input_dir / filename, 'r', encoding='utf-8') as f:
            return await f.read()

    async def process_all(self) -> None:
        """Process all eligible files in the input directory."""
        for file_path in self.input_dir.iterdir():
            filename = file_path.name
            
            if filename in self.files_in_process:
                continue
                
            if not self.should_process(filename):
                continue
                
            try:
                self.files_in_process.add(filename)
                await self.process_file(filename)
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}", flush=True)
                traceback.print_exc()
            finally:
                self.files_in_process.remove(filename)