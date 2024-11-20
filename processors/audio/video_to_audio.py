import os
from pathlib import Path
from moviepy import VideoFileClip

class VideoToAudioProcessor:
    """Extracts audio from video files and replaces the original file with the audio-only version."""

    def __init__(self, input_dir: Path, output_dir: Path):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def process_all(self) -> None:
        """Process all video files in the input directory."""
        for file_path in self.input_dir.iterdir():
            filename = file_path.name
            await self.process_single_file(filename)

    async def process_single_file(self, filename: str) -> None:
        """Process a single video file: extract audio and replace the original file."""
        input_path = self.input_dir / filename
        output_path = self.output_dir / f"{filename.rsplit('.', 1)[0]}.m4a"

        try:
            # Check if the file is a video file (e.g., .mkv, .mp4, .avi)
            _, ext = os.path.splitext(filename)
            if ext.lower() not in ['.mkv', '.mp4', '.avi']:
                return

            print(f"Extracting audio from: {filename}", flush=True)

            # Extract audio from the video file
            video = VideoFileClip(str(input_path))
            audio = video.audio
            audio.write_audiofile(str(output_path), codec="aac")
            video.close()
            audio.close()

            # Remove the original video file
            os.remove(input_path)

            print(f"Extracted audio: {output_path}", flush=True)
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}", flush=True)
            raise