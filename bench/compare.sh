#!/usr/bin/env bash
# Reproduce bench/RESULTS.md: one fresh venv per library, the same inputs, one report.
# Needs uv (https://docs.astral.sh/uv/). CAMeL Tools pulls in PyTorch (several GB): run this on a roomy machine.
set -euo pipefail
cd "$(dirname "$0")/.."
V=bench/.venvs
mkdir -p "$V" bench/results
declare -A PKG=([ours]="." [pyarabic]="pyarabic" [camel]="camel-tools" [maha]="mahad" [tashaphyne]="tashaphyne")
echo "{" > bench/results/sizes.json
first=1
for lib in ours pyarabic camel maha tashaphyne; do
  uv venv -q --clear -p 3.12 "$V/$lib"   # fresh, so sizes count only this library
  uv pip install -q -p "$V/$lib/bin/python" "${PKG[$lib]}"
  site=$("$V/$lib/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
  mb=$(du -sm "$site" | cut -f1)
  pkgs=$(($(uv pip list -p "$V/$lib/bin/python" 2>/dev/null | tail -n +3 | wc -l) - 1))   # dependencies, the library itself not counted
  [ $first = 1 ] || echo "," >> bench/results/sizes.json; first=0
  printf '"%s": {"mb": %s, "pkgs": %s}' "$lib" "$mb" "$pkgs" >> bench/results/sizes.json
  "$V/$lib/bin/python" -W ignore bench/compare.py --lib "$lib" > "bench/results/$lib.json"
  echo "$lib done"
done
echo "}" >> bench/results/sizes.json
python3 bench/compare.py --report bench/results/{ours,pyarabic,camel,maha,tashaphyne}.json --sizes bench/results/sizes.json > bench/RESULTS.md
echo "→ bench/RESULTS.md"
