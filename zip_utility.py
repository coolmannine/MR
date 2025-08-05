import os
import zipfile
from pathlib import Path
from typing import Union

__all__ = ["zip_two_folders"]


def zip_two_folders(zip_filename: Union[str, os.PathLike], folder1: Union[str, os.PathLike], folder2: Union[str, os.PathLike]) -> None:
    # removed docstring

    zip_filename = Path(zip_filename)
    folder1, folder2 = Path(folder1), Path(folder2)

    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(folder1):
            for file in files:
                full_path = Path(root) / file
                arcname = full_path.relative_to(folder1.parent)
                zf.write(full_path, arcname)
        for root, _, files in os.walk(folder2):
            for file in files:
                full_path = Path(root) / file
                arcname = full_path.relative_to(folder2.parent)
                zf.write(full_path, arcname)
    print(f"Created ZIP → {zip_filename}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Zip two sibling folders inside a single archive.")
    parser.add_argument("output", help="Path of zip file to create")
    parser.add_argument("folder1", help="First folder to include")
    parser.add_argument("folder2", help="Second folder to include")
    args = parser.parse_args()

    zip_two_folders(args.output, args.folder1, args.folder2) 