from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    # LLM
    exaone_model: str = "exaone3.5:7.8b"        # Ollama에 등록된 EXAONE 모델명
    claude_model: str = "claude-sonnet-4-6"
    perplexity_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""

    # VectorDB
    chroma_persist_dir: str = str(BASE_DIR / "data" / "vectordb")
    summary_collection: str = "ifp_summary"
    detail_collection: str = "ifp_detail"

    # LLM 분리: 가벼운 작업과 답변 생성 분리
    light_model: str = "exaone3.5:7.8b"      # formalizer/planner/review
    generator_model: str = "exaone3.5:32b"   # 답변 생성 전용 (4.5 확정 시 변경)
    embedding_model: str = "exaone3.5:7.8b"  # 절대 변경 금지 (DB 재생성 필요)

    # Retriever
    mmr_k: int = 5
    mmr_fetch_k: int = 20
    mmr_lambda: float = 0.6          # 다양성 vs 관련성 균형

    # RAG Loop
    max_iterations: int = 3

    # G2B 수집
    g2b_api_key: str = ""
    g2b_collect_days: int = 7          # 최근 N일 공고 수집
    g2b_min_budget: int = 30_000_000   # 최소 추정가격 (3천만원)
    g2b_keywords: list[str] = [
        "데이터", "빅데이터", "AI", "인공지능", "플랫폼",
        "데이터베이스", "정보화", "시스템 구축", "데이터 연계",
        "데이터 관리", "클라우드", "디지털", "스마트",
    ]

    # 경로
    raw_data_dir: str = str(BASE_DIR / "data" / "raw")
    chunks_dir: str = str(BASE_DIR / "data" / "chunks")
    announcements_dir: str = str(BASE_DIR / "data" / "announcements")

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"


settings = Settings()
