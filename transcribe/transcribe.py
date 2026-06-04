#!/usr/bin/env python3
"""Transcribe audio files using OpenAI Whisper API."""

import argparse
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
    parser = argparse.ArgumentParser(
        description="Transcribe audio files to markdown via OpenAI Whisper."
    )
    parser.add_argument(
        "source",
        nargs="?",
        help="Audio file or directory to transcribe (default: current directory)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output directory for transcripts (default: alongside source files)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.")
        sys.exit(1)

    source = Path(args.source) if args.source else Path.cwd()
    out_dir = Path(args.output) if args.output else None

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    if source.is_file():
        targets = [source] if source.suffix.lower() in AUDIO_EXTENSIONS else []
    else:
        targets = [
            p for p in sorted(source.iterdir())
            if p.suffix.lower() in AUDIO_EXTENSIONS
        ]

    if not targets:
        print("No audio files found.")
        sys.exit(0)

    for audio_path in targets:
        dest_dir = out_dir if out_dir else audio_path.parent
        md_path = dest_dir / audio_path.with_suffix(".md").name

        if md_path.exists():
            print(f"Skipping {audio_path.name} — {md_path.name} already exists")
            continue

        print(f"Transcribing {audio_path.name}...")
        text = transcribe(audio_path, api_key)
        md_path.write_text(f"# Transcript — {audio_path.stem}\n\n{text}\n")
        print(f"Saved → {md_path}")


if __name__ == "__main__":
    main()
