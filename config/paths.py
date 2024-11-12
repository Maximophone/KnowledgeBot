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
    ideas_directory: Path = vault_knowledgebot_path / "Ideas Directory.md"
    gdoc_path: Path = vault_path / "gdoc"
    markdownload_path: Path = vault_path / "MarkDownload"
    sources_path: Path = vault_path / "Source"
    source_template_path: Path = vault_path / "Templates" / "source.md"
    
    def __iter__(self):
        """Allow iteration over all paths for directory creation."""
        return iter([
            self.audio_input,
            self.audio_processed,
            self.transcriptions,
            self.meditations,
            self.ideas_directory.parent
        ])

PATHS = Paths()