import os
import shutil
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image

__all__ = [
    "convert_webp_to_jpg",
    "check_low_variation_images",
    "process_chapters",
]


def convert_webp_to_jpg(folder_path: str, delete_original: bool = True) -> None:
    webp_files: List[Path] = list(Path(folder_path).glob("*.webp")) + list(
        Path(folder_path).glob("*.WEBP")
    )

    if not webp_files:
        print("No WebP files found – skipping conversion.")
        return

    for path in webp_files:
        try:
            with Image.open(path) as img:
                jpg_path = path.with_suffix(".jpg")

                # Handle transparency for JPEG
                if img.mode in {"RGBA", "LA"}:
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    img = background

                img.save(jpg_path, "JPEG", quality=95)
                if delete_original:
                    path.unlink()
                print(f"Converted {path.name} → {jpg_path.name}")
        except Exception as exc:
            print(f"[ERROR] Failed converting {path.name}: {exc}")


def _has_low_variation(image_path: str, threshold: float) -> Tuple[bool, float]:
    img = cv2.imread(image_path)
    if img is None:
        return True, 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    std_dev = float(np.std(gray))
    return std_dev < threshold, std_dev


def check_low_variation_images(
    folder_path: str,
    *,
    std_threshold: float = 5.0,
    move_blanks: bool = True,
) -> None:
    low_var_folder = os.path.join(folder_path, "bad_images")
    if move_blanks:
        os.makedirs(low_var_folder, exist_ok=True)

    image_exts = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff")
    image_files = [f for f in os.listdir(folder_path) if f.lower().endswith(image_exts)]

    low_variation: List[Tuple[str, float]] = []
    for filename in image_files:
        full_path = os.path.join(folder_path, filename)
        if "bad_images" in full_path:
            continue
        is_low_var, std_dev = _has_low_variation(full_path, std_threshold)
        if is_low_var:
            low_variation.append((filename, std_dev))
            if move_blanks:
                shutil.move(full_path, os.path.join(low_var_folder, filename))
                print(f"Moved low-variation image ⇒ {filename}")

    if low_variation:
        print(f"Found {len(low_variation)} low-variation images in '{folder_path}'.")
    else:
        print("No low-variation images detected.")


def process_chapters(base_folder: str) -> None:
    chapters = sorted(
        (
            d
            for d in os.listdir(base_folder)
            if os.path.isdir(os.path.join(base_folder, d)) and d.lower().startswith("chapter")
        ),
        key=lambda name: int("".join(filter(str.isdigit, name))) or 0,
    )

    if not chapters:
        print("No chapter folders found.")
        return

    print(f"Processing {len(chapters)} chapter folders …")
    print("-" * 50)

    for chapter in chapters:
        chapter_path = os.path.join(base_folder, chapter)
        convert_webp_to_jpg(chapter_path)
        check_low_variation_images(chapter_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean-up chapter image folders.")
    parser.add_argument("base_folder", help="Root directory that contains chapter sub-folders")
    args = parser.parse_args()

    process_chapters(args.base_folder) 