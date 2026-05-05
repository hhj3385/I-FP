"""
신규 공고 수집 실행 스크립트

매일 실행 권장 (Windows 작업 스케줄러 또는 수동)
실행: python scripts/collect_new.py [--days N]

G2B API 키 설정:
  .env 파일에 추가 → G2B_API_KEY=여기에키입력
  발급: https://www.data.go.kr 에서 '나라장터 입찰공고정보 서비스' 신청
"""
import sys
import argparse
sys.path.insert(0, r"C:\Users\az200\I&FP")
sys.stdout.reconfigure(encoding="utf-8")

from datetime import datetime
from src.collectors.g2b_collector import collect, save_announcements, ingest_to_chroma
from config.settings import settings


def main():
    parser = argparse.ArgumentParser(description="G2B 신규 공고 수집")
    parser.add_argument("--days", type=int, default=None,
                        help=f"수집 기간(일), 기본={settings.g2b_collect_days}")
    parser.add_argument("--no-ingest", action="store_true",
                        help="ChromaDB 적재 생략 (JSON 저장만)")
    parser.add_argument("--dry-run", action="store_true",
                        help="실제 저장 없이 미리보기만")
    args = parser.parse_args()

    print(f"=== G2B 공고 수집 시작: {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")

    if not settings.g2b_api_key:
        print("⚠  G2B_API_KEY 가 설정되지 않았습니다.")
        print("   .env 파일에 다음 줄을 추가하세요:")
        print("   G2B_API_KEY=발급받은키\n")
        print("   API 키 발급: https://www.data.go.kr")
        print("   → '나라장터 입찰공고정보 서비스' 검색 → 활용신청\n")
        sys.exit(1)

    items = collect(args.days)

    if not items:
        print("새로운 관련 공고가 없습니다.")
        return

    print(f"\n수집된 공고 목록 ({len(items)}건):")
    for i, item in enumerate(items, 1):
        budget = item.get("presmptPrce", "미정")
        print(f"  {i:2d}. [{item.get('ntceInsttNm','')}] {item.get('bidNtceNm','')}")
        print(f"       마감: {item.get('bidClseDt','')} | 추정가: {budget}원")

    if args.dry_run:
        print("\n[DRY RUN] 저장 생략")
        return

    save_announcements(items)

    if not args.no_ingest:
        print("\nChromaDB 적재 중...")
        ingest_to_chroma(items)

    print(f"\n=== 완료: {len(items)}건 수집·적재 ===")


if __name__ == "__main__":
    main()
