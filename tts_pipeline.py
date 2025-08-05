import json
import logging
import os
import re
import base64
from pathlib import Path
from typing import List, Dict, Tuple

import requests
from pydub import AudioSegment

__all__ = ["TTSPipeline"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class TTSPipeline:
    # removed docstring
    def __init__(
        self,
        api_key: str,
        scripts_folder: str,
        output_folder: str = "output",
        voice_name: str = "en-US-Wavenet-D",
        max_ssml_length: int = 4900,
    ) -> None:
        self.api_key = api_key
        self.scripts_folder = scripts_folder
        self.base_output_folder = output_folder
        self.voice_name = voice_name
        self.max_ssml_length = max_ssml_length

        self.audio_folder = os.path.join(output_folder, "audio")
        self.timepoint_folder = os.path.join(output_folder, "timepoints")
        self.tts_url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={api_key}"

        os.makedirs(self.audio_folder, exist_ok=True)
        os.makedirs(self.timepoint_folder, exist_ok=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _split_ssml(self, ssml: str) -> List[str]:
        ssml = ssml.strip()
        if ssml.startswith("<speak>"):
            ssml = ssml[7:]
        if ssml.endswith("</speak>"):
            ssml = ssml[:-8]

        if len(ssml) <= self.max_ssml_length:
            return [f"<speak>{ssml}</speak>"]

        parts = re.split(r"(<mark name=\"[^\"]+\"/>)", ssml)
        chunks, current = [], ""
        for part in parts:
            if len(current) + len(part) > self.max_ssml_length:
                chunks.append(f"<speak>{current}</speak>")
                current = ""
            current += part
        if current:
            chunks.append(f"<speak>{current}</speak>")
        return chunks

    def _synthesize_chunk(self, ssml_chunk: str, mp3_out: Path) -> Dict:
        payload = {
            "input": {"ssml": ssml_chunk},
            "voice": {
                "languageCode": "en-US",
                "name": self.voice_name,
                "ssmlGender": "MALE",
            },
            "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.1},
            "enableTimePointing": ["SSML_MARK"],
        }

        response = requests.post(self.tts_url, json=payload)
        response.raise_for_status()
        data = response.json()
        if "audioContent" not in data:
            raise RuntimeError("No audio content in TTS response")

        audio_data = base64.b64decode(data["audioContent"])
        mp3_out.write_bytes(audio_data)
        duration = len(AudioSegment.from_file(mp3_out)) / 1000.0
        return {"duration": duration, "timepoints": data.get("timepoints", [])}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def process_chapter(self, txt_file: str, chapter_number: int) -> Tuple[str, List[Dict]]:
        # removed docstring
        audio_out = Path(self.audio_folder) / f"chapter{chapter_number}.mp3"
        timepoints_out = Path(self.timepoint_folder) / f"chapter{chapter_number}.json"
        temp_dir = Path(self.base_output_folder) / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        raw_text = Path(txt_file).read_text(encoding="utf-8").strip()
        ssml = f"<speak>{raw_text}</speak>"
        chunks = self._split_ssml(ssml)
        logging.info(f"Chapter {chapter_number}: {len(chunks)} SSML chunk(s)")

        chunk_files, global_timepoints, offset = [], [], 0.0
        for i, chunk in enumerate(chunks, 1):
            chunk_mp3 = temp_dir / f"chapter{chapter_number}_chunk{i}.mp3"
            result = self._synthesize_chunk(chunk, chunk_mp3)
            chunk_files.append(chunk_mp3)
            for tp in result["timepoints"]:
                global_timepoints.append({
                    "markName": tp["markName"],
                    "timeSeconds": offset + tp["timeSeconds"],
                })
            offset += result["duration"]

        combined = AudioSegment.silent(duration=0)
        for file in chunk_files:
            combined += AudioSegment.from_file(file)
        combined.export(audio_out, format="mp3")

        for f in chunk_files:
            f.unlink(missing_ok=True)
        temp_dir.rmdir()

        timepoints_out.write_text(json.dumps(global_timepoints, indent=2), encoding="utf-8")
        return str(audio_out), global_timepoints

    def process_all(self) -> List[Dict]:
        results = []
        txt_files = sorted(Path(self.scripts_folder).glob("*.txt"))
        for path in txt_files:
            chap_num = int(re.search(r"\d+", path.stem).group())
            try:
                mp3, tps = self.process_chapter(str(path), chap_num)
                results.append({"chapter": chap_num, "audio": mp3, "timepoints": len(tps)})
            except Exception as exc:
                logging.error(f"Failed processing chapter {chap_num}: {exc}")
        return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Batch convert narration scripts into MP3 with time-points.")
    parser.add_argument("api_key", help="Google Cloud TTS API key")
    parser.add_argument("scripts", help="Folder containing *.txt narration scripts")
    parser.add_argument("--out", default="output", help="Output directory for audio & timepoints")
    args = parser.parse_args()

    pipeline = TTSPipeline(args.api_key, args.scripts, args.out)
    summary = pipeline.process_all()
    print("\nProcessing summary:")
    for item in summary:
        print(f"Chapter {item['chapter']}: {item['audio']} ({item['timepoints']} marks)") 