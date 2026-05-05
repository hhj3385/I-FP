"""
제안 아카이브 → data/raw/ 준비 스크립트

동작:
1. 제안 아카이브 내 모든 .zip 재귀 압축 해제
2. 텍스트 추출 가능한 파일만 data/raw/ 에 복사
3. 이미지·영상·폰트 등 불필요 파일 스킵 (복사 안 함)
"""
import sys
import io
import zipfile
import shutil
from pathlib import Path

# Windows 콘솔 UTF-8 출력
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ARCHIVE_DIR = Path("C:/Users/az200/I&FP/제안 아카이브")
RAW_DIR     = Path("C:/Users/az200/I&FP/data/raw")
UNZIP_DIR   = Path("C:/Users/az200/I&FP/data/_unzipped")  # 임시 압축 해제 위치

# 복사할 확장자 (텍스트 추출 가능)
COPY_EXTS = {".hwp", ".hwpx", ".pdf", ".pptx", ".ppt", ".xlsx", ".xls", ".docx", ".txt", ".md"}

# 완전히 무시할 확장자
SKIP_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".svg", ".ico",
    ".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v",
    ".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    ".exe", ".dll", ".msi", ".bat", ".sh",
    ".ini", ".cfg", ".log", ".db", ".sqlite",
    ".lnk", ".url", ".ds_store",
}


def unzip_all(src: Path, dest: Path, depth: int = 0):
    """ZIP 파일을 재귀적으로 모두 압축 해제"""
    indent = "  " * depth
    for zip_path in sorted(src.rglob("*.zip")):
        rel = zip_path.relative_to(src)
        target = dest / rel.parent / zip_path.stem
        if target.exists():
            continue
        try:
            target.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as z:
                # 한글 파일명 인코딩 처리
                for member in z.infolist():
                    try:
                        member.filename = member.filename.encode("cp437").decode("euc-kr")
                    except Exception:
                        try:
                            member.filename = member.filename.encode("utf-8").decode("utf-8")
                        except Exception:
                            pass
                    try:
                        z.extract(member, target)
                    except Exception:
                        pass
            print(f"{indent}[OK] 압축 해제: {rel}")
        except Exception as e:
            print(f"{indent}[WARN] 실패: {rel} ({e})")


def copy_useful_files(src: Path, dest: Path):
    """텍스트 추출 가능한 파일만 dest로 복사 (중복 파일명 자동 처리)"""
    dest.mkdir(parents=True, exist_ok=True)
    copied, skipped, unknown = 0, 0, 0
    name_count: dict[str, int] = {}

    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()

        if ext in SKIP_EXTS:
            skipped += 1
            continue

        if ext not in COPY_EXTS:
            unknown += 1
            continue

        # 중복 파일명 처리: 같은 이름이면 _2, _3 ... 붙임
        stem, suffix = path.stem, path.suffix
        key = (stem + suffix).lower()
        if key in name_count:
            name_count[key] += 1
            dest_name = f"{stem}_{name_count[key]}{suffix}"
        else:
            name_count[key] = 1
            dest_name = stem + suffix

        try:
            shutil.copy2(path, dest / dest_name)
            copied += 1
        except Exception as e:
            print(f"  [FAIL] 복사 실패: {path.name} ({e})")

    return copied, skipped, unknown


if __name__ == "__main__":
    print("=" * 60)
    print("STEP 1. ZIP 압축 해제")
    print("=" * 60)
    UNZIP_DIR.mkdir(parents=True, exist_ok=True)

    # 아카이브 폴더 자체의 zip들 먼저 해제
    unzip_all(ARCHIVE_DIR, UNZIP_DIR)
    # 해제된 결과 안에 또 zip이 있을 수 있으므로 한 번 더
    unzip_all(UNZIP_DIR, UNZIP_DIR)
    print("압축 해제 완료\n")

    print("=" * 60)
    print("STEP 2. 유효 파일 복사 → data/raw/")
    print("=" * 60)

    # 이미 폴더로 존재하는 항목(압축 없이 올라온 것)도 포함
    copied1, skipped1, unk1 = copy_useful_files(ARCHIVE_DIR, RAW_DIR)
    copied2, skipped2, unk2 = copy_useful_files(UNZIP_DIR, RAW_DIR)

    total_copied  = copied1 + copied2
    total_skipped = skipped1 + skipped2
    total_unknown = unk1 + unk2

    print(f"""
결과 요약
─────────────────────────────
  복사 완료  : {total_copied:,}개
  스킵 (이미지/영상/폰트) : {total_skipped:,}개
  미인식 형식 : {total_unknown:,}개
  저장 위치   : {RAW_DIR}
─────────────────────────────
""")
    print("완료! 이제 python -m src.retrievers.ingest 를 실행하세요.")
