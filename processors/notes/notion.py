from pathlib import Path
from typing import Dict, Tuple
import aiofiles
import os

from .base import NoteProcessor
from ..common.frontmatter import parse_frontmatter_from_content, frontmatter_to_text
from config.logging_config import setup_logger
from integrations.notion_integration import NotionClient


logger = setup_logger(__name__)


def _split_frontmatter_and_body(markdown_text: str) -> Tuple[Dict, str]:
    """Split a markdown document into (frontmatter_dict, body_markdown).

    If no frontmatter is present, returns ({}, original_text).
    """
    if not markdown_text.startswith("---"):
        return {}, markdown_text

    lines = markdown_text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        # Not a frontmatter block
        return {}, markdown_text

    # Find the closing '---' line
    closing_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing_index = index
            break

    if closing_index is None:
        # Malformed frontmatter; treat as no frontmatter
        return {}, markdown_text

    # Parse frontmatter using the shared utility
    frontmatter_dict = parse_frontmatter_from_content(markdown_text)
    body_markdown = "".join(lines[closing_index + 1 :])
    return frontmatter_dict, body_markdown


class NotionProcessor(NoteProcessor):
    """Synchronizes Obsidian notes with Notion pages.

    - If frontmatter contains `push_to_notion`, create a new Notion page under that parent.
    - Otherwise, if `url` refers to a Notion page, pull and merge Notion properties.
    """

    stage_name = "notion_synced"

    def __init__(self, input_dir: Path):
        super().__init__(input_dir)
        self.notion = NotionClient()

    def should_process(self, filename: str, frontmatter: Dict) -> bool:
        if not frontmatter:
            return False

        # Deprecated, here for backward-compatibility
        if frontmatter.get("synced"):
            return False

        # Explicit push request
        if frontmatter.get("push_to_notion"):
            return True

        # Process if it has a URL pointing to Notion
        url = frontmatter.get("url")
        if not url:
            return False

        return "notion.so" in url or "notion.site" in url or "notion" in url

    async def process_file(self, filename: str) -> None:
        logger.info("Processing Notion sync: %s", filename)

        content = await self.read_file(filename)
        local_frontmatter = parse_frontmatter_from_content(content)

        # Push flow: create a page from the markdown body in a parent URL
        if local_frontmatter.get("push_to_notion"):
            # Extract content body (exclude frontmatter from body for upload consistency)
            parts = content.split("---", 2)
            if len(parts) >= 3:
                body_md = parts[2]
            else:
                body_md = content

            parent_url = local_frontmatter.get("push_to_notion")
            title = filename.replace(".md", "")

            try:
                page_response = self.notion.create_page_from_markdown(
                    markdown_content=body_md,
                    parent_url=parent_url,
                    title=title,
                )
                # The integration returns a dict with fields like 'id' and 'url'.
                notion_url = None
                notion_id = None
                if isinstance(page_response, dict):
                    notion_url = page_response.get("url")
                    notion_id = page_response.get("id")
                elif isinstance(page_response, str):
                    # Back-compat: sometimes integrations return just an id or url
                    if page_response.startswith("http"):
                        notion_url = page_response
                    else:
                        notion_id = page_response

                # Store reference to the remote page for future pulls
                if notion_url:
                    local_frontmatter["url"] = notion_url
                elif notion_id:
                    # Fallback: store id if URL not available
                    local_frontmatter["url"] = notion_id

                if notion_id:
                    local_frontmatter["notion_page_id"] = notion_id

                # And to the parent page
                local_frontmatter["parent_url"] = parent_url
                # Remove push directive after success
                local_frontmatter.pop("push_to_notion", None)
            except Exception as e:
                logger.error("Error creating Notion page for %s: %s", filename, str(e))
                raise

            # Mark as synced and write file back unchanged body
            local_frontmatter["synced"] = True
            final_content = frontmatter_to_text(local_frontmatter) + body_md

            async with aiofiles.open(self.input_dir / filename, 'w', encoding='utf-8') as f:
                await f.write(final_content)
            os.utime(self.input_dir / filename, None)
            logger.info("Pushed to Notion and updated file: %s", filename)
            return

        # Pull flow: fetch page from Notion and merge properties
        try:
            notion_markdown = self.notion.fetch_page_as_markdown(local_frontmatter["url"])
        except Exception as e:
            logger.error("Error fetching Notion page for %s: %s", filename, str(e))
            raise

        # Extract properties (frontmatter) and page content from Notion MD
        notion_properties, notion_body = _split_frontmatter_and_body(notion_markdown)

        # Merge: override only the keys provided by Notion's properties
        merged_frontmatter = dict(local_frontmatter)
        for key, value in notion_properties.items():
            merged_frontmatter[key] = value

        # Mark as synced
        merged_frontmatter["synced"] = True

        final_content = frontmatter_to_text(merged_frontmatter) + notion_body

        async with aiofiles.open(self.input_dir / filename, 'w', encoding='utf-8') as f:
            await f.write(final_content)
        os.utime(self.input_dir / filename, None)

        logger.info("Pulled from Notion and merged properties: %s", filename)


