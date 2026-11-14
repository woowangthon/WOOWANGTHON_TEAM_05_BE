import os
import secrets

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.models import Profile, ProfilePatch, Revision
from app.planner import build_plan, interpret_demo

load_dotenv()
app = FastAPI(title="온보딩 · 정착 계획 API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=[s.strip() for s in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if s.strip()], allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-API-Key"])


def authenticate(x_api_key: str = Header(default="")):
    expected = os.getenv("BACKEND_API_KEY", "")
    if expected and not secrets.compare_digest(expected, x_api_key):
        raise HTTPException(401, "인증 정보를 확인해 주세요.")


async def call_ai(endpoint: str, body: dict) -> dict:
    base = os.getenv("AI_SERVICE_URL", "").rstrip("/")
    if not base:
        raise HTTPException(503, "Gemma 서버가 설정되지 않았습니다.")
    try:
        async with httpx.AsyncClient(timeout=75) as client:
            response = await client.post(base + endpoint, json=body, headers={"X-API-Key": os.getenv("AI_API_KEY", "")})
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Gemma 서버에서 응답을 받지 못했습니다. 연결과 모델 상태를 확인해 주세요.") from exc


async def enrich(plan: dict) -> dict:
    if not os.getenv("AI_SERVICE_URL"):
        return plan
    # Send only the conditions relevant to planning; no company/name/nationality.
    context = {"options": [{k: h[k] for k in ("id", "monthly", "commute", "monthly_missing")} for h in plan["options"]],
               "guides": [{k: g[k] for k in ("id", "title", "text")} for g in plan["guides"]]}
    try:
        result = await call_ai("/explain", context)
        focus = result.get("focus")
        ids = result.get("source_ids", [])
        allowed = {g["id"] for g in plan["guides"]}
        if focus not in ("budget", "commute", "checklist") or not isinstance(ids, list) or any(not isinstance(i, str) or i not in allowed for i in ids):
            raise HTTPException(503, "검증되지 않은 Gemma 응답")
        # Model selects the explanation focus and evidence. All facts and URLs stay server-owned.
        plan["mode"] = "gemma"
        plan["explanation_source_ids"] = ids
        label = {"budget": "비용", "commute": "통근", "checklist": "준비 절차"}[focus]
        plan["explanation"] = "Gemma가 " + label + " 중심으로 계획을 정리했습니다. 공개 시작 요금과 참고 예산을 사용하며, 원문에서 실제 계약 조건과 통근 경로를 확인하세요."
    except HTTPException:
        plan["warnings"].append("Gemma 설명 생성에 실패하여 규칙 기반 결과를 표시합니다. 모델이 응답한 결과가 아닙니다.")
    return plan


@app.get("/health")
def health():
    return {"status": "ok", "ai_configured": bool(os.getenv("AI_SERVICE_URL")), "data": "sourced_snapshot"}


@app.post("/api/plans", dependencies=[Depends(authenticate)])
async def create_plan(profile: Profile):
    return await enrich(build_plan(profile))


@app.post("/api/plans/revise", dependencies=[Depends(authenticate)])
async def revise_plan(request: Revision):
    try:
        if os.getenv("AI_SERVICE_URL"):
            result = await call_ai("/interpret", {"message": request.message, "profile": request.profile.model_dump(mode="json")})
            patch = ProfilePatch.model_validate(result.get("changes", {})).changes()
            if not patch:
                raise ValueError("변경할 조건을 찾지 못했습니다. 예산·통근시간·주거 형태를 구체적으로 입력해 주세요.")
        else:
            patch = interpret_demo(request.message)
        # Revalidate the complete profile after model output is applied.
        profile = Profile.model_validate({**request.profile.model_dump(mode="json"), **patch})
    except (ValueError, ValidationError) as exc:
        raise HTTPException(422, str(exc)) from exc
    plan = await enrich(build_plan(profile))
    plan["changes"] = patch
    return plan
