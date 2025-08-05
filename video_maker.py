import concurrent.futures
import json
import os
import subprocess
from pathlib import Path
from typing import List

from moviepy.editor import AudioFileClip, ImageClip, CompositeVideoClip

__all__ = ["create_chapter_video", "process_all_chapters"]


# ------------------------------------------------------------
# helpers
# ------------------------------------------------------------

def _load_timepoints(path: Path) -> List[float]:
    with path.open() as f:
        points = json.load(f)
    points.sort(key=lambda x: x["timeSeconds"])
    return [p["timeSeconds"] for p in points]


def create_chapter_video(
    chapter_num: int,
    *,
    audio_dir: Path,
    timepoints_dir: Path,
    chapters_dir: Path,
    output_dir: Path,
    transparent: bool = False,
    fps: int = 10,
) -> None:
    print(f"\n📖 Processing Chapter {chapter_num}")

    audio_path = audio_dir / f"chapter{chapter_num}.mp3"
    timepoints_path = timepoints_dir / f"chapter{chapter_num}.json"
    img_folder = chapters_dir / f"chapter{chapter_num}"

    if not audio_path.exists() or not timepoints_path.exists():
        print(f"❌ Missing files for Chapter {chapter_num}")
        return

    temp_ext = ".mov" if transparent else ".mp4"
    temp_video = Path(f"temp_chapter{chapter_num}{temp_ext}")
    final_video = output_dir / f"chapter{chapter_num}{temp_ext}"

    audio_clip = AudioFileClip(str(audio_path))
    duration_total = audio_clip.duration

    transitions = _load_timepoints(timepoints_path)

    images = sorted(
        [img for img in img_folder.iterdir() if img.name[0].isdigit()],
        key=lambda p: int(p.stem.split("-")[0]),
    )
    if not images:
        print(f"❌ No images for Chapter {chapter_num}")
        return

    if len(images) < len(transitions):
        transitions = transitions[: len(images)]

    transitions.insert(0, 0.0)
    transitions.append(duration_total)

    clips = []
    for idx in range(len(transitions) - 1):
        if idx >= len(images):
            break
        start, end = transitions[idx], transitions[idx + 1]
        dur = end - start
        if dur <= 0:
            continue
        clip = ImageClip(str(images[idx])).set_start(start).set_duration(dur)
        clips.append(clip)

    print(f"🎬 Creating video for Chapter {chapter_num}…")
    video = CompositeVideoClip(clips, size=clips[0].size)
    video = video.set_audio(audio_clip).set_duration(duration_total)

    codec = "png" if transparent else "libx264"

    video.write_videofile(
        str(temp_video),
        fps=fps,
        codec=codec,
        audio_codec="aac",
        preset="ultrafast",
        threads=os.cpu_count(),
    )
    video.close()
    audio_clip.close()

    print(f"🚀 Finalising Chapter {chapter_num} with FFmpeg…")
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-threads",
        str(os.cpu_count()),
        "-i",
        str(temp_video),
        "-i",
        str(audio_path),
        "-c:v",
        ("qtrle" if transparent else "libx264"),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(final_video),
    ]
    subprocess.run(ffmpeg_cmd, check=True)
    temp_video.unlink(missing_ok=True)
    print(f"✅ Saved → {final_video}")


# ------------------------------------------------------------
# batch processing
# ------------------------------------------------------------

def process_all_chapters(
    *,
    audio_dir: Path,
    timepoints_dir: Path,
    chapters_dir: Path,
    output_dir: Path,
    transparent: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    chapters = [int(p.stem[7:]) for p in sorted(audio_dir.glob("chapter*.mp3"))]
    with concurrent.futures.ProcessPoolExecutor() as ex:
        futs = [
            ex.submit(
                create_chapter_video,
                ch,
                audio_dir=audio_dir,
                timepoints_dir=timepoints_dir,
                chapters_dir=chapters_dir,
                output_dir=output_dir,
                transparent=transparent,
            )
            for ch in chapters
        ]
        for f in concurrent.futures.as_completed(futs):
            try:
                f.result()
            except Exception as exc:
                print(f"❌ Error: {exc}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create chapter videos from images + audio")
    parser.add_argument("audio", help="Folder with chapterX.mp3 files")
    parser.add_argument("timepoints", help="Folder with chapterX.json timepoints")
    parser.add_argument("chapters", help="Folder with chapter image sub-folders")
    parser.add_argument("output", help="Destination folder for videos")
    parser.add_argument("--transparent", action="store_true", help="Export with alpha channel (MOV)")
    args = parser.parse_args()

    process_all_chapters(
        audio_dir=Path(args.audio),
        timepoints_dir=Path(args.timepoints),
        chapters_dir=Path(args.chapters),
        output_dir=Path(args.output),
        transparent=args.transparent,
    ) 