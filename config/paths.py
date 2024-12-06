from pathlib import Path
from dataclasses import dataclass

@dataclass
class Paths:
    # Base paths
    knowledgebot_path: Path = Path("G:/My Drive/KnowledgeBot")
    vault_path: Path = Path("G:/My Drive/Obsidian")
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
    markdownload_path: Path = vault_path / "MarkDownload"
    sources_path: Path = vault_path / "Source"
    source_template_path: Path = vault_path / "Templates" / "source.md"
    meetings: Path = vault_path / "Meetings"
    meeting_template: Path = vault_path / "Templates" / "meeting.md"
    conversations: Path = vault_path / "Conversations"
    diary: Path = vault_path / "Diary"

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
            self.markdownload_path,
            self.sources_path,
            self.meetings,
            self.conversations,
            self.diary
        ])

PATHS = Paths()