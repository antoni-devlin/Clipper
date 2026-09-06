import subprocess
import os
import json
import sys
from pathlib import Path
import platform

def get_project_dir():
    if platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    project_dir = base / "ux-clipper"
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir

def get_audio_dir():
    if platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    audio_dir = base / "ux-clipper" / "audio_files"
    audio_dir.mkdir(parents=True, exist_ok=True)
    return audio_dir

def get_transcript_dir():
    if platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    transcript_dir = base / "ux-clipper" / "transcript_files"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    return transcript_dir

def get_clips_dir():
    if platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    clips_dir = base / "ux-clipper" / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    return clips_dir

def get_ffmpeg_path():
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "ffmpeg")
    return "ffmpeg"  # dev mode — relies on PATH, as before


def cleanPath(longPath):
    cleanPath = longPath.split("/")[-1].split(".")[0]
    return cleanPath


def extract_audio(videoPath):
    if os.path.exists(videoPath):
        outputPath = str(get_audio_dir() / (cleanPath(videoPath) + ".wav"))
        if os.path.exists(outputPath):
            print(f"Audio file already exists ({outputPath}), using existing file")
            return outputPath
        else:
            print(f"Converting video file to 16KHz, mono, .wav file")
            try:
                subprocess.run(
                    [
                        get_ffmpeg_path(),
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        "-i",
                        videoPath,
                        "-vn",
                        "-ar",
                        "16000",
                        "-ac",
                        "1",
                        outputPath,
                    ],
                    check=True,
                    capture_output=True,
                )
                return outputPath
            except subprocess.CalledProcessError as e:
                print(e.stderr.decode())
                raise
    else:
        raise Exception(f"Problem with file path. Does the video file exist?")

if platform.system() == "Darwin":
    import mlx_whisper

    def run_transcription(audio_path):
        return mlx_whisper.transcribe(audio_path)
else:
    from faster_whisper import WhisperModel

    _model = None

    def run_transcription(audio_path):
        global _model
        if _model is None:
            _model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = _model.transcribe(audio_path)
        # faster-whisper returns an iterator of segment objects, not dicts —
        # normalize to the same shape your JSON-writing code already expects
        return {"segments": [{"start": s.start, "end": s.end, "text": s.text} for s in segments]}

def transcribe_audio(audioPath):
    transcriptPath = str(
        get_transcript_dir() / (cleanPath(audioPath) + "-transcript.json")
    )
    if os.path.exists(transcriptPath):
        print(f"File already transcribed ({transcriptPath}), using exisiting file")
        return transcriptPath
    else:
        transcript = run_transcription(audioPath)
        for segment in transcript["segments"]:
            print(segment)
        print(f"Writing transcript to {transcriptPath}")
        json_data = json.dumps(transcript["segments"], indent=4)
        with open(transcriptPath, "w") as f:
            f.write(json_data)
        return transcriptPath

def cut_clip(inputVideoPath, start: str, end: str, clipTitle):
    outputClipPath = str(get_clips_dir() / f"{clipTitle}.mp4")
    try:
        subprocess.run(
            [
                get_ffmpeg_path(),
                "-ss",
                start,
                "-to",
                end,
                "-i",
                inputVideoPath,
                "-c",
                "copy",
                f"{outputClipPath}",
            ],
            check=True,
            capture_output=True,
        )
        return outputClipPath
    except subprocess.CalledProcessError as e:
        print(e.stderr.decode())
        raise


if __name__ == "__main__":
    main()
