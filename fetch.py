# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "curl-cffi>=0.7",
#   "beautifulsoup4>=4.12",
#   "markdownify>=0.11",
#   "pydantic>=2.0",
# ]
# ///
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fetcher import fetch_job

if len(sys.argv) < 2:
    print("Uso: uv run fetch.py 'https://...'", file=sys.stderr)
    sys.exit(1)

url = sys.argv[1]

try:
    job = fetch_job(url, description_format="markdown")
except Exception as e:
    print(f"Erro: {e}", file=sys.stderr)
    sys.exit(1)

d = job.to_dict()
for key, value in d.items():
    if value is None:
        continue
    if key == "description":
        print(f"\n{'─'*60}")
        print("DESCRIÇÃO:")
        print(value)
    else:
        print(f"{key}: {value}")
