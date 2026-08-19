from pathlib import Path

page_path = Path(r"c:\Users\hp hay\OneDrive\سطح المكتب\ImaginAI\frontend\src\app\page.tsx")
content = page_path.read_text(encoding="utf-8")

lines = content.splitlines()

open_divs = 0
open_parens = 0

for idx, line in enumerate(lines, 1):
    div_opens = line.count("<div")
    div_closes = line.count("</div>")
    open_divs += (div_opens - div_closes)
    
    if "screen ===" in line or "isCaptionModalOpen &&" in line or "isFeedbackOpen &&" in line:
        print(f"Line {idx}: {line.strip()} (Current open divs: {open_divs})")

print(f"\nFinal open divs count: {open_divs}")
