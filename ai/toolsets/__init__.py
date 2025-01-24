from . import test, system, coda, memory, linkedin, obsidian, gmail, subagents

# Define available tool sets
TOOL_SETS = {
    "test": test.TOOLS,
    "system": system.TOOLS,
    "coda": coda.TOOLS,
    "memory": memory.TOOLS,
    "linkedin": linkedin.TOOLS,
    "obsidian": obsidian.TOOLS,
    "gmail": gmail.TOOLS,
    "subagents": subagents.TOOLS
} 