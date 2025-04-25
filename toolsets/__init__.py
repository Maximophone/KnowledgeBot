from . import gmail, linkedin, memory, obsidian, subagents, system, test, vector_db, discord
from . import coda

# Define available tool sets
TOOL_SETS = {
    "test": test.TOOLS,
    "system": system.TOOLS,
    "coda": coda.TOOLS,
    "memory": memory.TOOLS,
    "linkedin": linkedin.TOOLS,
    "obsidian": obsidian.TOOLS,
    "gmail": gmail.TOOLS,
    "subagents": subagents.TOOLS,
    "vector_db": vector_db.TOOLS,
    "discord": discord.TOOLS
} 