# transcribe

Transcribe audio files to markdown using OpenAI Whisper.

## Usage

```bash
# Transcribe all audio files in current directory
transcribe

# Transcribe a specific file
transcribe recording.m4a
```

Outputs a `.md` file alongside each audio file. Skips files that already have a transcript.

## Supported formats

`.m4a`, `.mp3`, `.mp4`, `.wav`, `.webm`, `.ogg`, `.flac`

## Setup

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=your-key
```

### Install globally

```bash
cp transcribe.py ~/.local/bin/transcribe
chmod +x ~/.local/bin/transcribe
```
