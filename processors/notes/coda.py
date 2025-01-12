from pathlib import Path
from typing import Dict
import aiofiles
from .base import NoteProcessor
from ..common.frontmatter import parse_frontmatter, frontmatter_to_text
from integrations.coda_integration import CodaClient
import os
from config.secrets import CODA_API_KEY

class CodaProcessor(NoteProcessor):
    """Processes Coda pages by pulling their content and converting to markdown."""
    
    def __init__(self, input_dir: Path):
        super().__init__(input_dir)
        self.stage_name = "coda_synced"
        self.coda_client = CodaClient(CODA_API_KEY)
        
    def should_process(self, filename: str, frontmatter: Dict) -> bool:        
        if not frontmatter:
            return False
        
        # Process if it has a URL and it's a Coda URL
        url = frontmatter.get("url")
        if not url:
            return False
            
        return "coda.io" in url
        
    async def process_file(self, filename: str) -> None:
        print(f"Processing coda page: {filename}", flush=True)
        
        # Read the file
        content = await self.read_file(filename)
        frontmatter = parse_frontmatter(content)
        
        try:
            # Extract doc and page IDs from URL
            doc_id, page_id = self.coda_client.extract_doc_and_page_id(frontmatter["url"])
            
            # Get page content directly in markdown format
            coda_content_md = self.coda_client.get_page_content(doc_id, page_id, output_format="markdown")
            
            # Update frontmatter and save
            final_content = frontmatter_to_text(frontmatter) + coda_content_md.decode('utf-8')
            
            # Write back to same file
            async with aiofiles.open(self.input_dir / filename, 'w', encoding='utf-8') as f:
                await f.write(final_content)
            os.utime(self.input_dir / filename, None)

            print(f"Processed coda page: {filename}", flush=True)
            
        except Exception as e:
            print(f"Error processing Coda page {filename}: {str(e)}", flush=True)
            raise 