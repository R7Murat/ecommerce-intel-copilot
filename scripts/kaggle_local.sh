#!/usr/bin/env bash
# Local profile on a Kaggle GPU: Ollama + gpt-oss:20b, traces written to a file.
# Run in a Kaggle notebook (GPU T4 x2, Internet on) from the cloned repo root:
#   !git clone --depth 1 --branch v3 https://github.com/R7Murat/ecommerce-intel-copilot.git
#   %cd ecommerce-intel-copilot
#   !bash scripts/kaggle_local.sh [low|medium|high|default]
# Needs a Kaggle dataset with products.db and the chroma/ folder attached as input.
set -euo pipefail
EFFORT="${1:-default}"
OUT=/kaggle/working

# Data: input datasets are read-only and Chroma writes to its folder, so copy.
DB=$(find /kaggle/input -name products.db -print -quit)
CHROMA=$(dirname "$(find /kaggle/input -name chroma.sqlite3 -print -quit)")
[ -f "$DB" ] && [ -d "$CHROMA" ] || { echo "attach a dataset with products.db and chroma/"; exit 1; }
mkdir -p data && cp "$DB" data/products.db && rm -rf data/chroma && cp -r "$CHROMA" data/chroma

pip install -q -r requirements.txt

# Ollama: local only, model pulled once per session (~13 GB).
command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
export OLLAMA_NO_CLOUD=1 OLLAMA_CONTEXT_LENGTH=8192
nohup ollama serve > "$OUT/ollama.log" 2>&1 &
for _ in $(seq 30); do curl -sf http://localhost:11434/api/version >/dev/null && break; sleep 2; done
ollama pull gpt-oss:20b
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv

export COPILOT_PROFILE=local COPILOT_TRACES_FILE="$OUT/traces_local.otlp" PYTHONPATH=src
rm -f "$COPILOT_TRACES_FILE"
python scripts/trace_demo.py
python scripts/smoke.py "$EFFORT"
cp eval_results/smoke_*_local_*.json "$OUT/"
ollama ps
echo "Download from $OUT: traces_local.otlp and smoke_*_local_*.json"
