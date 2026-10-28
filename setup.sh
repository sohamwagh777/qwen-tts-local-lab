#!/usr/bin/env bash
# One-time / idempotent setup for the Qwen TTS local lab.
set -euo pipefail
cd "$(dirname "$0")"

command -v uv >/dev/null || { echo "install uv first: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }

if [ ! -d .venv ]; then
  echo "==> creating python 3.12 venv"
  uv venv --python 3.12 .venv
fi

echo "==> installing pytorch (cu129 = the only working Blackwell-ARM build; harmless capability warning on GB10)"
uv pip install --python .venv/bin/python --index-url https://download.pytorch.org/whl/cu129 torch==2.8.0 torchaudio==2.8.0

echo "==> installing qwen-tts"
uv pip install --python .venv/bin/python qwen-tts soundfile

if [ ! -d Qwen3-TTS-Tokenizer-12Hz ]; then
  echo "==> downloading tokenizer (~651 MB)"
  uvx --from huggingface_hub hf download Qwen/Qwen3-TTS-Tokenizer-12Hz --local-dir Qwen3-TTS-Tokenizer-12Hz
fi
if [ ! -d Qwen3-TTS-12Hz-1.7B-CustomVoice ]; then
  echo "==> downloading model (~4.3 GB)"
  uvx --from huggingface_hub hf download Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice --local-dir Qwen3-TTS-12Hz-1.7B-CustomVoice
fi

echo "==> verifying"
.venv/bin/python -c "import torch; assert torch.cuda.is_available(), 'no GPU'; print('torch', torch.__version__, 'gpu:', torch.cuda.get_device_name(0))"
.venv/bin/python -c "import qwen_tts, soundfile; print('qwen_tts OK')"
echo "SETUP COMPLETE — run ./run.sh"
