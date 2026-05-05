"""company_info 폴더 파일들 텍스트 추출 → 출력"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\az200\I&FP")

from pathlib import Path
from src.retrievers.ingest import EXTRACTORS

info_dir = Path(r"C:\Users\az200\I&FP\company_info")
for path in sorted(info_dir.iterdir()):
    ext = path.suffix.lower()
    if ext not in EXTRACTORS:
        print(f"[SKIP] {path.name}")
        continue
    try:
        text = EXTRACTORS[ext](path)
        print(f"\n{'='*60}")
        print(f"[파일] {path.name} ({len(text):,}자)")
        print('='*60)
        print(text[:3000])
        if len(text) > 3000:
            print(f"\n... (이하 {len(text)-3000:,}자 생략)")
    except Exception as e:
        print(f"[ERROR] {path.name}: {e}")
