import sys
from pathlib import Path

def parse_qat(filepath):
    lines = Path(filepath).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if not line.strip(): continue
        indent = len(line) - len(line.lstrip())
        print(f"{i+1:02d} [{indent:02d}] {line.strip()}")

if __name__ == "__main__":
    parse_qat(r"c:\Users\user\Desktop\ThreatModelwFlask\TM-Questions\QaT.txt")
