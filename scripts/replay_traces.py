"""Send a COPILOT_TRACES_FILE (one base64 OTLP batch per line) to Langfuse.

Usage: PYTHONPATH=src python scripts/replay_traces.py traces.otlp
Spans keep their original timestamps and attributes (profile, model, server address).
"""
import base64
import sys
import urllib.request

from dotenv import load_dotenv

from copilot.observability import langfuse_exporter_args

load_dotenv(".env")
args = langfuse_exporter_args()
if not args:
    raise SystemExit("set LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY in .env")

sent = 0
for line in open(sys.argv[1], encoding="ascii"):
    if not line.strip():
        continue
    req = urllib.request.Request(
        args["endpoint"], data=base64.b64decode(line), method="POST",
        headers={**args["headers"], "Content-Type": "application/x-protobuf"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status >= 300:
            raise SystemExit(f"batch {sent + 1}: HTTP {resp.status}")
    sent += 1
print(f"sent {sent} batches to {args['endpoint']}")
