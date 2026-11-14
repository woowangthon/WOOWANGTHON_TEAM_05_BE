# 온보딩 — 해외 정착 도우미 · Backend

2026 AI 우왕톤 05팀 **우짤래**. FastAPI가 입력 검증, 공식 안내 검색, 주거 필터링, 통근 조회, 비용 계산, 체크리스트와 재계획을 담당합니다.

## 실행

Python 3.12 이상과 [uv](https://docs.astral.sh/uv/)가 필요합니다.

```sh
uv sync --locked --group dev
uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- API 문서: http://127.0.0.1:8000/docs
- GET `/health`: 서버와 AI 설정 여부 (Gemma 준비 상태는 AI `/health`로 별도 확인)
- POST `/api/plans`: Profile JSON → 계획
- POST `/api/plans/revise`: `{ "profile": { ... }, "message": "더 저렴하게, 통근 60분" }` → 재계획·변경 필드

`tests/test_api.py`의 PROFILE이 완전한 요청 예시입니다. 도시·근무 지역·주거 형태는 명시한 열거형만 허용하며, 예산·보험료·시간은 서버에서 재검증합니다.

## Gemma 연결

`.env.example`을 `.env`로 복사하고 설정합니다.

```dotenv
AI_SERVICE_URL=http://127.0.0.1:8001
AI_API_KEY=
BACKEND_API_KEY=
CORS_ORIGINS=http://localhost:3000
```

AI_SERVICE_URL이 없으면 명확히 표시한 규칙 기반 데모가 실행됩니다. 주소가 있으면 AI 게이트웨이의 `/interpret`, `/explain`을 사용합니다. 조건 해석 실패는 503/422로 반환하고 기존 계획을 유지하게 합니다. 설명 실패는 데모 상태와 warnings에 표시합니다.

모델은 비용을 계산하거나 URL을 만들지 않습니다. 변경 필드를 허용 목록과 Pydantic으로 검증한 뒤 전체 Profile을 다시 검증합니다. 설명은 모델이 선택한 초점과 등록된 출처 ID를 검증하고 서버가 표현합니다. 작은 공식 문서 corpus의 메타데이터 검색이며 벡터 DB는 사용하지 않습니다.

AI Studio 무료 API를 사용하려면 AI 저장소의 `.env`에 `AI_PROVIDER=google`, `GEMINI_API_KEY`, `GEMMA_MODEL=gemma-4-26b-a4b-it`를 설정합니다. Google 키는 AI 서버에만 보관하며 `AI_API_KEY`와는 별개입니다. 설정과 무료 한도는 [AI README](../WOOWANGTHON_TEAM_05_AI/README.md)를 참고하세요.

## Docker로 BE·AI 실행

이 저장소와 AI 저장소를 같은 부모 폴더에 받습니다. Docker 실행 환경에서:

```sh
docker compose up --build -d
```

기본 연결은 Google AI Studio이며 AI 폴더의 `.env`를 읽습니다. Docker Compose 2.24.0 이상이 필요합니다. 서버 간 `AI_API_KEY`는 BE 폴더의 `.env`에서 전달합니다.

로컬 Ollama를 사용하려면 AI `.env`를 `AI_PROVIDER=ollama`, `GEMMA_MODEL=gemma3:4b`로 설정하고 다음 명령을 사용하세요.

```sh
docker compose --profile local up --build -d
docker compose exec ollama ollama pull gemma3:4b
```

로컬 모델 다운로드는 별도이며 GPU가 없으면 CPU 추론이 느릴 수 있습니다. GPU 설정은 실행 환경에 맞게 추가하세요. Docker 구성은 로컬 시연용이며 실제 실행 검증은 별도입니다.

## 비용·데이터

`app/data/sydney.json`의 매물·월세·통근·생활비는 모두 **가상 데이터**입니다. 원문 URL이 있는 것은 공식 생활·행정 안내입니다. 실제 매물 링크를 꾸며 만들지 않습니다.

- 주간 월세 × 52 ÷ 12, 소수 둘째 자리까지 반올림하여 월 환산.
- 월 알려진 지출: 환산 월세 + 교통 + 식비 + 공과금 + 통신 + 입력한 보험료.
- 초기 알려진 지출: 확인된 보증금 + 선납 월세 + 가상 이사비. 항공권·비자·기타 비용은 별도 확인.
- 미확인 비용은 목록으로 기록하고 부분 합계로 표시. 월 지출과 초기 비용을 서로 더하지 않음.
- 순위 균형 점수는 `월 지출 + 편도 통근분 × 10`의 시연용 휴리스틱. 최저 비용·최단 통근 정렬도 지원.
- 국적·비자 상태·체류 목적은 참고 정보이며 비자 자격을 확정하지 않음.

FE와 fixture를 함께 갱신해야 합니다. FE의 `tests/integration.mjs`로 27가지 조건의 응답 일치 여부를 확인할 수 있습니다.

## 검증·배포

```sh
uv run python -m pytest -q
```

공개 서비스에서는 BACKEND_API_KEY와 AI_API_KEY를 설정하고 TLS·허용 출처를 실제 배포에 맞게 지정하세요. FE에 같은 BACKEND_API_KEY를 서버 환경 변수로 설정합니다. API는 현재 상태를 저장하지 않으며 계정·DB·예약 기능이 없습니다.

공식 안내 출처·확인일은 fixture의 guides에 있습니다. [FE](https://github.com/woowangthon/WOOWANGTHON_TEAM_05_FE), [AI](https://github.com/woowangthon/WOOWANGTHON_TEAM_05_AI) README를 함께 참고하세요.
