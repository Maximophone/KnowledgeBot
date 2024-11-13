from pathlib import Path
import aiofiles
from .base import NoteProcessor
from ..common.frontmatter import parse_frontmatter
from ai import AI, get_prompt


class MarkdownloadProcessor(NoteProcessor):
    """Processes downloaded web pages and creates source notes with summaries."""
    
    def __init__(self, input_dir: Path, output_dir: Path, template_path: Path):
        super().__init__(input_dir)
        self.stage_name = "markdownload_summarised"
        self.output_dir = output_dir
        self.template_path = template_path
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.prompt_summary = get_prompt("summarise_markdownload")
        
    def should_process(self, filename: str) -> bool:
        if not (filename.startswith("markdownload_") and filename.endswith(".md")):
            return False
            
        # Check if output file exists
        new_filename = filename[13:]  # Remove "markdownload_" prefix
        return not (self.output_dir / new_filename).exists()
        
    async def process_file(self, filename: str) -> None:
        print(f"Processing markdownload: {filename}", flush=True)
        
        # Read source file
        content = await self.read_file(filename)
        frontmatter = parse_frontmatter(content)
        
        # Generate summary
        summary = self.ai_model.message(
            self.prompt_summary + content
        )
        
        # Read template
        async with aiofiles.open(self.template_path, 'r', encoding='utf-8') as f:
            template = await f.read()
        
        # Prepare new filename and content
        new_filename = filename[13:]  # Remove "markdownload_" prefix
        fname = filename.split(".")[0]
        
        if frontmatter:
            url = frontmatter.get("url", "")
            template = template.replace("url: ", f"url: {url}")
            template = template.replace("{{title}}", new_filename.split(".")[0])
            template = template.replace("markdownload:", f'markdownload: "[[{fname}]]"')
        
        # Save to output directory
        output_path = self.output_dir / new_filename
        async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
            await f.write(template + "\n" + summary)
            
        print(f"Processed markdownload: {filename}", flush=True)