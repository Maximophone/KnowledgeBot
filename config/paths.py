from pathlib import Path
from dataclasses import dataclass

@dataclass
class Paths:
    # Base paths
    knowledgebot_path: Path = Path("G:/My Drive/KnowledgeBot")
    vault_path: Path = Path("G:/My Drive/Obsidian")
    runtime_path: Path = Path(".")
    vault_knowledgebot_path: Path = vault_path / "KnowledgeBot"
    
    # Audio processing paths
    audio_input: Path = knowledgebot_path / "Audio" / "Incoming"
    audio_processed: Path = knowledgebot_path / "Audio" / "Processed"
    transcriptions: Path = vault_knowledgebot_path / "Transcriptions"
    
    # Note processing paths
    meditations: Path = vault_knowledgebot_path / "Meditations"
    ideas: Path = vault_knowledgebot_path / "Ideas"
    ideas_directory: Path = vault_knowledgebot_path / "Ideas Directory.md"
    todo_directory: Path = vault_knowledgebot_path / "Todo Directory.md"
    gdoc_path: Path = vault_path / "gdoc"
    coda_path: Path = vault_path / "coda"
    markdownload_path: Path = vault_path / "MarkDownload"
    sources_path: Path = vault_path / "Source"
    source_template_path: Path = vault_path / "Templates" / "source.md"
    meetings: Path = vault_path / "Meetings"
    meeting_template: Path = vault_path / "Templates" / "meeting.md"
    conversations: Path = vault_path / "Conversations"
    diary: Path = vault_path / "Diary"
    people_path: Path = vault_path / "People" # People directory path
    
    scripts_folder: Path = vault_path / "scripts"

    # prompts
    prompts_library: Path = vault_path / "Prompts"

    # AI memory paths
    ai_memory: Path = vault_path / "AI Memory"
    
    # LinkedIn paths
    linkedin_messages: Path = vault_path / "LinkedIn Messages"

    # data
    data: Path = runtime_path / "data"

    obsidian_vector_db: Path = runtime_path / "data/obsidian_vector_db.sqlite"
    
    # Google Drive paths
    meetings_gdrive_folder_id: str = "13tFGdok5I-UTlE-3_We7W1Yym_iV7SK7"

    def __iter__(self):
        """Allow iteration over all paths for directory creation."""
        return iter([
            self.audio_input,
            self.audio_processed,
            self.transcriptions,
            self.meditations,
            self.ideas,
            self.ideas_directory.parent,
            self.gdoc_path,
            self.coda_path,
            self.markdownload_path,
            self.sources_path,
            self.meetings,
            self.conversations,
            self.diary,
            self.ai_memory,
            self.linkedin_messages,
            self.people_path
        ])
    
PATHS = Paths()