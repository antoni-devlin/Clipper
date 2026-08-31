import subprocess
import os
import json

os.environ["HF_HUB_OFFLINE"] = "1"
import mlx_whisper

video = "./videos/usability-testing-demo.mp4"

def cleanPath(longPath):
    cleanPath = longPath.split("/")[-1].split(".")[0]
    return cleanPath

def extract_audio(videoPath):
    if os.path.exists(videoPath):
        outputPath = "./audio_files/"+cleanPath(videoPath)+".wav"
        if os.path.exists(outputPath):
            print(f'Audio file already exists ({outputPath}), using existing file')
            return outputPath
        else:
            print(f'Converting video file to 16KHz, mono, .wav file')
            subprocess.run(
            ["ffmpeg", "-i", videoPath, "-vn", "-ar", "16000", "-ac", "1", outputPath],
            check=True,
            capture_output=True,
        )
        return outputPath
    else:
        raise Exception(f'Problem with file path. Does this file exist?\n{video}')

def transcribe_audio(audioPath):
    transcriptPath = './transcripts/'+cleanPath(audioPath)+'-transcript.json'
    if os.path.exists(transcriptPath):
        print(f'File already transcribed ({transcriptPath}), using exisiting file')
        return transcriptPath
    else:
        transcript = mlx_whisper.transcribe(audioPath)
        for segment in transcript["segments"]:
            print(segment)
        print(f'Writing transcript to {transcriptPath}')
        json_data = json.dumps(transcript["segments"], indent=4)
        with open(transcriptPath, "w") as f:
            f.write(json_data)
        return transcriptPath

def cut_clip(inputVideoPath, start:str, end:str, transcriptFile, clipTitle):
    outputClipPath = f'./clips/{clipTitle}.mp4'
    subprocess.run(["ffmpeg", "-ss", start, "-to", end, "-i", inputVideoPath, "-c", "copy", f'{outputClipPath}'])
    return outputClipPath

def main():
    extracted_audio = extract_audio(video)
    transcript = transcribe_audio(extracted_audio)
    cut_clip(video, "00:00:00", "00:00:05", transcript, "struggling with browse page")

if __name__ == "__main__":
    main()
