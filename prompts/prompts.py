def get_prompt(prompt_name: str) -> str:
    with open(f"prompts/{prompt_name}.md", "r") as f:
        return f.read()