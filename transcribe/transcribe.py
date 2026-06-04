#!/usr/bin/env python3
"""Transcribe audio files in this folder using OpenAI Whisper API."""

import os
import sys
from pathlib import Path

AUDIO_EXTENSIONS = {".m4a", ".mp3", ".mp4", ".wav", ".webm", ".ogg", ".flac"}


def transcribe(audio_path: Path, api_key: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="text",
        )
    return result.strip()


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.")
        sys.exit(1)

    folder = Path.cwd()

    # If a specific file is passed as argument, use that; otherwise scan folder
    if len(sys.argv) > 1:
        targets = [Path(sys.argv[1])]
    else:
        targets = [
            p for p in sorted(folder.iterdir())
            if p.suffix.lower() in AUDIO_EXTENSIONS
        ]

    if not targets:
        print("No audio files found.")
        sys.exit(0)

    for audio_path in targets:
        md_path = audio_path.with_suffix(".md")
        if md_path.exists():
            print(f"Skipping {audio_path.name} — {md_path.name} already exists")
            continue

        print(f"Transcribing {audio_path.name}...")
        text = transcribe(audio_path, api_key)

        md_path.write_text(f"# Transcript — {audio_path.stem}\n\n{text}\n")
        print(f"Saved → {md_path.name}")


if __name__ == "__main__":
    main()
