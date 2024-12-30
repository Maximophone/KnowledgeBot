import re
import fitz

def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            blocks = page.get_text("blocks")
            for block in blocks:
                block_text = block[4]
                block_text = re.sub(r'-\n', '', block_text)
                block_text = re.sub(r'(?<!\n)\n(?!\n)', ' ', block_text)
                block_text = re.sub(r'\s+', ' ', block_text)
                text += block_text.strip() + "\n\n"

    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    return text 