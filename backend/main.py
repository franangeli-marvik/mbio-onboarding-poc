import asyncio
import json
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from livekit import api
from livekit.api import LiveKitAPI
from pydantic import BaseModel

from core.config import livekit_url, livekit_api_key, livekit_api_secret
from core.extraction import (
    extract_profile_from_transcript,
    extract_profile_features,
    convert_to_profile_format,
)
from core.enhancement import enhance_resume, convert_resume_to_profile
from interview_prep import run_interview_prep_pipeline
from resume.parser import parse_resume, get_mime_type
from storage import get_storage
from tenants.loader import load_tenant

_livekit_api: LiveKitAPI | None = None


async def _get_livekit_api() -> LiveKitAPI:
    global _livekit_api
    if _livekit_api is None:
        _livekit_api = LiveKitAPI(
            url=livekit_url().replace("wss://", "https://").replace("ws://", "http://"),
            api_key=livekit_api_key(),
            api_secret=livekit_api_secret(),
        )
    return _livekit_api


app = FastAPI(
    title="MBIO Voice Agent API",
    description="Backend API for voice-based profile creation",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


VOICE_QUESTIONS = {
    "school": [
        {
            "id": "major",
            "question": "What's your major or degree?",
            "subtext": "Tell us what you're studying.",
            "conditional": {"dependsOn": "lifeStage", "values": ["student"]},
        },
        {
            "id": "university",
            "question": "Which university do you attend?",
            "conditional": {"dependsOn": "lifeStage", "values": ["student"]},
        },
        {
            "id": "jobTitle",
            "question": "What's your current or most recent job title?",
            "conditional": {"dependsOn": "lifeStage", "values": ["recent_grad", "professional"]},
        },
        {
            "id": "company",
            "question": "Which company or organization?",
            "conditional": {"dependsOn": "lifeStage", "values": ["recent_grad", "professional"]},
        },
        {
            "id": "bigWin",
            "question": "Tell us about your biggest accomplishment.",
            "subtext": "Don't worry about perfect grammar - just tell us what happened and what you're proud of.",
        },
        {
            "id": "academicHistory",
            "question": "Any academic awards, honors, or relevant coursework?",
            "subtext": "Dean's List, scholarships, key projects - anything that stands out.",
        },
    ],
    "life": [
        {
            "id": "xFactorCategory",
            "question": "Outside work and school, how do you spend your time?",
            "subtext": "Tell me about your main area of interest - sports, volunteering, creative arts, tech projects, travel, or something else?",
        },
        {
            "id": "xFactorDetail",
            "question": "Tell us about a specific achievement or role in that area.",
            "subtext": "What did you accomplish? What role did you play?",
        },
        {
            "id": "xFactorLessons",
            "question": "What valuable lessons did you learn?",
            "subtext": "How do these experiences connect to your goals?",
        },
    ],
    "skills": [
        {
            "id": "hardSkills",
            "question": "What are your top 5 tools or technical skills?",
            "subtext": "The software, languages, or technical abilities you use most.",
        },
        {
            "id": "softSkillsFriend",
            "question": "How would your best friend describe you in three words?",
            "subtext": "Think about what they'd say about your personality.",
        },
        {"id": "softSkillsSelf", "question": "How would you describe yourself in three words?"},
    ],
    "impact": [
        {
            "id": "legacyStatement",
            "question": "What impact do you want to make?",
            "subtext": "Think big - how do you want to change your industry, community, or the world?",
        },
        {
            "id": "socialLinks",
            "question": "Where else can people find you?",
            "subtext": "LinkedIn, GitHub, portfolio site, Instagram - any relevant URLs.",
        },
    ],
}

PHASES_ORDER = ["school", "life", "skills", "impact"]

ALLOWED_MIME_TYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
]


class TokenRequest(BaseModel):
    room_name: str
    participant_name: str
    participant_identity: str | None = None
    interview_briefing: dict | None = None
    interview_plan: dict | None = None


class TokenResponse(BaseModel):
    token: str
    url: str
    room_name: str


class ExtractProfileRequest(BaseModel):
    transcript: list[dict]


class QuestionResponse(BaseModel):
    questions: list[dict]
    phase: str
    total_questions: int


class GenerateProfileRequest(BaseModel):
    basics_answers: dict
    transcript: list[dict]
    session_id: str | None = None


class EnhanceResumeRequest(BaseModel):
    resume_data: dict
    transcript: list[dict]
    profile_analysis: dict | None = None
    basics_answers: dict | None = None


class PrepareInterviewRequest(BaseModel):
    resume_data: dict
    life_stage: str
    user_name: str
    tenant_id: str | None = None
    position_id: str | None = None


@app.get("/")
async def root():
    return {"service": "MBIO Voice Agent API", "status": "running", "version": "2.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/tenant/{tenant_id}")
async def get_tenant(tenant_id: str):
    try:
        tenant = load_tenant(tenant_id)
        return {
            "tenant_id": tenant.tenant_id,
            "company_name": tenant.company_name,
            "tone": tenant.tone,
            "positions": [
                {"id": p.id, "title": p.title, "focus_area": p.focus_area}
                for p in tenant.positions
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Tenant not found: {e}")


@app.post("/api/token", response_model=TokenResponse)
async def generate_token(request: TokenRequest):
    try:
        identity = request.participant_identity or request.participant_name
        token = (
            api.AccessToken(livekit_api_key(), livekit_api_secret())
            .with_identity(identity)
            .with_name(request.participant_name)
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=request.room_name,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                )
            )
        )
        jwt_token = token.to_jwt()

        try:
            lk_api = await _get_livekit_api()
            room_metadata = {
                "participant_name": request.participant_name,
                "created_at": datetime.now().isoformat(),
            }
            has_briefing = request.interview_briefing is not None
            has_plan = request.interview_plan is not None
            if request.interview_briefing:
                room_metadata["interview_briefing"] = request.interview_briefing
            if request.interview_plan:
                room_metadata["interview_plan"] = request.interview_plan
            metadata_json = json.dumps(room_metadata)
            print(f"[TOKEN] Creating room {request.room_name} | briefing={has_briefing} | plan={has_plan} | metadata_size={len(metadata_json)}")
            await lk_api.room.create_room(
                api.CreateRoomRequest(
                    name=request.room_name,
                    metadata=metadata_json,
                )
            )
            print(f"[TOKEN] Room created successfully")
        except Exception as e:
            print(f"[TOKEN] Room creation FAILED: {e}")

        return TokenResponse(token=jwt_token, url=livekit_url(), room_name=request.room_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate token: {e}")


@app.get("/api/voice-questions", response_model=QuestionResponse)
async def get_voice_questions(phase: str, life_stage: Optional[str] = None):
    phase_lower = phase.lower()
    if phase_lower not in VOICE_QUESTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid phase. Valid phases: {list(VOICE_QUESTIONS.keys())}",
        )

    questions = _filter_questions(VOICE_QUESTIONS[phase_lower], life_stage)
    return QuestionResponse(questions=questions, phase=phase_lower, total_questions=len(questions))


@app.get("/api/voice-questions/all")
async def get_all_voice_questions(life_stage: Optional[str] = None):
    result = {
        phase: _filter_questions(VOICE_QUESTIONS[phase], life_stage)
        for phase in PHASES_ORDER
    }
    return {
        "phases": PHASES_ORDER,
        "questions_by_phase": result,
        "total_questions": sum(len(q) for q in result.values()),
    }


@app.post("/api/extract-profile")
async def extract_profile(request: ExtractProfileRequest):
    try:
        profile = extract_profile_from_transcript(request.transcript)
        return {"success": True, "profile": profile}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile extraction failed: {e}")


@app.post("/api/generate-profile")
async def generate_profile_from_interview(request: GenerateProfileRequest):
    try:
        extracted = extract_profile_features(
            transcript=request.transcript,
            basics_answers=request.basics_answers,
        )
        profile = convert_to_profile_format(extracted)
        return {"success": True, "profile": profile, "extracted_features": extracted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile generation failed: {e}")


@app.post("/api/enhance-resume")
async def enhance_resume_endpoint(request: EnhanceResumeRequest):
    try:
        original_profile = convert_resume_to_profile(request.resume_data)
        enhanced_profile = enhance_resume(
            resume_data=request.resume_data,
            transcript=request.transcript,
            profile_analysis=request.profile_analysis,
            basics_answers=request.basics_answers,
        )
        return {
            "success": True,
            "original": original_profile,
            "enhanced": enhanced_profile,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Resume enhancement failed: {e}")


@app.get("/api/sessions")
async def list_sessions():
    storage = get_storage()
    session_ids = storage.list_sessions()
    sessions = []

    for sid in session_ids:
        data = storage.load_json(sid, "session")
        if data:
            sessions.append(
                {
                    "session_id": data.get("session_id", sid),
                    "room_name": data.get("room_name"),
                    "timestamp": data.get("timestamp"),
                    "duration": data.get("duration", {}).get("formatted"),
                    "has_audio": data.get("audio_file") is not None,
                    "transcript_count": len(data.get("transcript", [])),
                }
            )

    return {"sessions": sessions}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    storage = get_storage()
    data = storage.load_json(session_id, "session")

    if not data:
        raise HTTPException(status_code=404, detail="Session not found")

    data["audio_available"] = storage.get_artifact_path(session_id, "audio") is not None
    return data


@app.get("/api/sessions/{session_id}/audio")
async def get_session_audio(session_id: str):
    storage = get_storage()
    audio_path = storage.get_artifact_path(session_id, "audio")

    if not audio_path:
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(audio_path, media_type="audio/ogg", filename=f"{session_id}.ogg")


@app.post("/api/prepare-interview")
async def prepare_interview(request: PrepareInterviewRequest):
    try:
        result = await run_interview_prep_pipeline(
            resume_data=request.resume_data,
            life_stage=request.life_stage,
            user_name=request.user_name,
            tenant_id=request.tenant_id,
            position_id=request.position_id,
        )
        return {
            "success": True,
            "interview_briefing": result.get("interview_briefing"),
            "profile_analysis": result.get("profile_analysis"),
            "interview_plan": result.get("interview_plan"),
            "errors": result.get("errors", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to prepare interview: {e}")


@app.post("/api/process-resume")
async def process_resume(
    file: UploadFile = File(...),
    linkedin_url: Optional[str] = Form(None),
):
    mime_type = file.content_type
    if mime_type not in ALLOWED_MIME_TYPES:
        try:
            mime_type = get_mime_type(file.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB")

    try:
        extracted_data = await asyncio.to_thread(
            parse_resume, file_bytes=file_bytes, mime_type=mime_type, filename=file.filename
        )
        _inject_linkedin(extracted_data, linkedin_url)
        return {
            "success": True,
            "data": extracted_data,
            "gaps_to_explore": extracted_data.get("_mbio", {}).get("gaps_to_explore", []),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process resume: {e}")


@app.post("/api/process-resume-and-prepare")
async def process_resume_and_prepare_interview(
    file: UploadFile = File(...),
    tenant_id: str = Form(...),
    position_id: str = Form(...),
    linkedin_url: str | None = Form(None),
):
    mime_type = file.content_type
    if mime_type not in ALLOWED_MIME_TYPES:
        try:
            mime_type = get_mime_type(file.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB")

    try:
        extracted_data = await asyncio.to_thread(
            parse_resume, file_bytes=file_bytes, mime_type=mime_type, filename=file.filename
        )
        _inject_linkedin(extracted_data, linkedin_url)

        user_name = extracted_data.get("basics", {}).get("name", "Candidate")

        prep_result = await run_interview_prep_pipeline(
            resume_data=extracted_data,
            life_stage="professional",
            user_name=user_name,
            tenant_id=tenant_id,
            position_id=position_id,
        )

        return {
            "success": True,
            "resume_data": extracted_data,
            "interview_briefing": prep_result.get("interview_briefing"),
            "profile_analysis": prep_result.get("profile_analysis"),
            "interview_plan": prep_result.get("interview_plan"),
            "pipeline_errors": prep_result.get("errors", []),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to process resume and prepare interview: {e}"
        )


def _filter_questions(questions: list[dict], life_stage: str | None) -> list[dict]:
    if not life_stage:
        return questions
    return [
        q
        for q in questions
        if not q.get("conditional") or life_stage in q["conditional"].get("values", [])
    ]


def _inject_linkedin(extracted_data: dict, linkedin_url: str | None) -> None:
    if not linkedin_url or not linkedin_url.strip():
        return

    extracted_data.setdefault("basics", {})
    extracted_data["basics"].setdefault("profiles", [])

    linkedin_exists = any(
        p.get("network", "").lower() == "linkedin"
        for p in extracted_data["basics"]["profiles"]
    )
    if not linkedin_exists:
        extracted_data["basics"]["profiles"].append(
            {"network": "LinkedIn", "url": linkedin_url.strip()}
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
