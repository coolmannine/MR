import os
import re
from pathlib import Path

__all__ = ["replace_asterisks_with_marks"]


_marker_tpl = "<mark name=\"p{0}\"/>"


def replace_asterisks_with_marks(file_path: str) -> None:
    content = Path(file_path).read_text(encoding="utf-8")
    counter = 1

    def _sub(_: re.Match[str]):
        nonlocal counter
        repl = _marker_tpl.format(counter)
        counter += 1
        return repl

    updated = re.sub(r"\*", _sub, content)
    Path(file_path).write_text(updated, encoding="utf-8")
    print(f"Updated file → {file_path} ({counter - 1} marks)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert asterisks to numbered <mark> tags in narration scripts.")
    parser.add_argument("folder", help="Folder containing *.txt scripts to process")
    args = parser.parse_args()

    for txt in Path(args.folder).glob("*.txt"):
        replace_asterisks_with_marks(str(txt)) 