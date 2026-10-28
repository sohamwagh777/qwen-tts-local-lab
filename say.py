#!/usr/bin/env python3
"""say_qwen.py — manual CLI for Qwen3-TTS CustomVoice (learn-by-hand tool).

Examples:
  .venv/bin/python say_qwen.py "Hello there, welcome to the lab." -o hello.wav
  .venv/bin/python say_qwen.py "नमस्ते दोस्तों!" -l Auto -s Ryan -i "Speak warmly and slowly" -o hi.wav
  .venv/bin/python say_qwen.py "Watch this!" -s Vivian -i "特别愤怒的语气" -o angry.wav

Speakers: Vivian Serena Uncle_Fu Dylan Eric Ryan Aiden Ono_Anna Sohee
Languages: Auto Chinese English Japanese Korean German French Russian Portuguese Spanish Italian
"""
import argparse
import time
from pathlib import Path

import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

HERE = Path(__file__).parent
MODEL = str(HERE / "Qwen3-TTS-12Hz-1.7B-CustomVoice")

_cache = {}


def get_model():
    if "m" not in _cache:
        t0 = time.time()
        _cache["m"] = Qwen3TTSModel.from_pretrained(
            MODEL, device_map="cuda:0", dtype=torch.bfloat16,
            attn_implementation="sdpa",
        )
        print(f"[model loaded in {time.time()-t0:.1f}s]", flush=True)
    return _cache["m"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("-o", "--out", default="out.wav")
    ap.add_argument("-s", "--speaker", default="Ryan")
    ap.add_argument("-l", "--language", default="Auto")
    ap.add_argument("-i", "--instruct", default=None)
    a = ap.parse_args()

    m = get_model()
    t0 = time.time()
    wavs, sr = m.generate_custom_voice(
        text=a.text, language=a.language, speaker=a.speaker,
        instruct=a.instruct,
    )
    sf.write(a.out, wavs[0], sr)
    print(f"{a.out}  sr={sr}  dur={len(wavs[0])/sr:.1f}s  took={time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
