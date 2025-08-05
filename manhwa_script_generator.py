import base64
import io
import os
import time
from pathlib import Path
from typing import List

from PIL import Image
import anthropic

from image_processing import convert_webp_to_jpg, check_low_variation_images

__all__ = ["ManhwaScriptGenerator"]


class ManhwaScriptGenerator:
    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 666,
        temperature: float = 0.0,
    ) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    @staticmethod
    def encode_image(image_path: str, scale: float = 0.27, min_dimension: int = 100) -> dict:
        extension = Path(image_path).suffix.lower()
        save_format = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}.get(
            extension, "PNG"
        )

        with Image.open(image_path) as img:
            width, height = img.size
            new_w = max(int(width * scale), min_dimension)
            new_h = max(int(height * scale), min_dimension)
            if new_w == min_dimension:
                new_h = int(height * (min_dimension / width))
            elif new_h == min_dimension:
                new_w = int(width * (min_dimension / height))

            img = img.resize((new_w, new_h), Image.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format=save_format)
            img_b64 = base64.b64encode(buffer.getvalue()).decode()

        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": f"image/{save_format.lower()}",
                "data": img_b64,
            },
        }

    @staticmethod
    def validate_response(resp: str, expected: int = 5) -> str:
        lines = [ln.strip() for ln in resp.split("*") if ln.strip()]
        if len(lines) != expected:
            raise ValueError(
                f"Expected {expected} lines but received {len(lines)} from Anthropic."
            )
        return resp

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------
    def process_chapters(
        self,
        chapters_dir: str,
        manhwa_name: str,
        scripts_out: str = "scripts",
    ) -> None:

        os.makedirs(scripts_out, exist_ok=True)

        # Initial seed messages (taken from the notebook’s original prompt)
        initial_messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": manhwa_name}],
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Chain of Thought Summary:\n"  # truncated, can be extended …
                        ),
                    }
                ],
            },
            {"role": "user", "content": [{"type": "text", "text": "intro"}]},
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "In a world where power knows no bounds, imagine being the strongest martial "
                            "artist alive …"
                        ),
                    }
                ],
            },
        ]

        base_messages = initial_messages.copy()

        for chapter_name in sorted(os.listdir(chapters_dir)):
            if chapter_name == ".ipynb_checkpoints":
                continue
            chapter_path = os.path.join(chapters_dir, chapter_name)
            if not os.path.isdir(chapter_path):
                continue

            print(f"Processing {chapter_name} …")
            img_files = sorted(
                [f for f in os.listdir(chapter_path) if f.lower().endswith((".jpg", ".jpeg", ".png"))],
                key=lambda x: int(x.split("-")[0]),
            )

            responses: List[str] = []
            messages = base_messages.copy()

            # Split into batches of 5 images
            for i in range(0, len(img_files), 5):
                batch = img_files[i : i + 5]
                batch_payload = [self.encode_image(os.path.join(chapter_path, img)) for img in batch]
                messages.append({"role": "user", "content": batch_payload})
                time.sleep(5)  # small delay for rate-limit friendliness

                reply = self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    temperature=self._temperature,
                    system="CRITICAL REQUIREMENT: YOU MUST ALWAYS OUTPUT EXACTLY 5 LINES, EACH ENDING WITH *",
                    messages=messages,
                )
                content_text = reply.content[0].text if isinstance(reply.content, list) else reply.content
                self.validate_response(content_text)
                messages.append({"role": "assistant", "content": [{"type": "text", "text": content_text}]})
                responses.append(content_text)

                # Keep context size in check (20 additional messages)
                if len(messages) > len(base_messages) + 20:
                    messages = base_messages + messages[-20:]

            # Persist chapter script
            script_path = os.path.join(scripts_out, f"{chapter_name}.txt")
            with open(script_path, "w", encoding="utf-8") as fp:
                fp.write("\n\n".join(responses))
            print(f"Saved script for {chapter_name} → {script_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate manhwa narration scripts via Anthropic.")
    parser.add_argument("chapters", help="Directory containing chapter sub-folders with images")
    parser.add_argument("api_key", help="Anthropic API key")
    parser.add_argument("manhwa_name", help="Title of the manhwa")
    parser.add_argument("--out", default="scripts", help="Output folder for .txt scripts")
    args = parser.parse_args()

    gen = ManhwaScriptGenerator(api_key=args.api_key)
    gen.process_chapters(args.chapters, args.manhwa_name, scripts_out=args.out) 