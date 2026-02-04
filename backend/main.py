"""
FastAPI Backend for MBIO Voice Agent
Provides endpoints for LiveKit token generation and voice interview orchestration.
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from livekit import api
from livekit.api import LiveKitAPI
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# SECRET MANAGEMENT - Uses Google Secret Manager in production, .env for local
# =============================================================================

def get_secret(secret_id: str, fallback_env: str = None) -> str:
    """
    Get secret from Google Secret Manager, with fallback to environment variable.
    
    In production (GCP): reads from Secret Manager
    In local dev: reads from .env file
    """
    # First try environment variable (for local development)
    env_value = os.getenv(fallback_env or secret_id.upper().replace("-", "_"))
    if env_value:
        return env_value
    
    # Try Google Secret Manager (for production)
    try:
        from google.cloud import secretmanager
        
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "mbio-profile-creation")
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"[WARN] Could not get secret '{secret_id}' from Secret Manager: {e}")
        return None


# Load configuration from secrets
LIVEKIT_URL = get_secret("livekit-url", "LIVEKIT_URL")
LIVEKIT_API_KEY = get_secret("livekit-api-key", "LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = get_secret("livekit-api-secret", "LIVEKIT_API_SECRET")

if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET]):
    raise ValueError("Missing required secrets: livekit-url, livekit-api-key, livekit-api-secret")

print(f"[INFO] Loaded secrets successfully. LiveKit URL: {LIVEKIT_URL[:30]}...")

# =============================================================================

# Initialize LiveKit API client for agent dispatch
livekit_api: LiveKitAPI | None = None

async def get_livekit_api() -> LiveKitAPI:
    """Get or create LiveKit API client"""
    global livekit_api
    if livekit_api is None:
        livekit_api = LiveKitAPI(
            url=LIVEKIT_URL.replace("wss://", "https://").replace("ws://", "http://"),
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
        )
    return livekit_api

app = FastAPI(
    title="MBIO Voice Agent API",
    description="Backend API for voice-based profile creation",
    version="1.0.0"
)

# CORS configuration - allow all origins for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=False,  # Must be False when allow_origins is "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# Voice interview questions organized by phase
VOICE_QUESTIONS = {
    "school": [
        {
            "id": "major",
            "question": "What's your major or degree?",
            "subtext": "Tell us what you're studying.",
            "conditional": {"dependsOn": "lifeStage", "values": ["student"]}
        },
        {
            "id": "university",
            "question": "Which university do you attend?",
            "conditional": {"dependsOn": "lifeStage", "values": ["student"]}
        },
        {
            "id": "jobTitle",
            "question": "What's your current or most recent job title?",
            "conditional": {"dependsOn": "lifeStage", "values": ["recent_grad", "professional"]}
        },
        {
            "id": "company",
            "question": "Which company or organization?",
            "conditional": {"dependsOn": "lifeStage", "values": ["recent_grad", "professional"]}
        },
        {
            "id": "bigWin",
            "question": "Tell us about your biggest accomplishment.",
            "subtext": "Don't worry about perfect grammar - just tell us what happened and what you're proud of."
        },
        {
            "id": "academicHistory",
            "question": "Any academic awards, honors, or relevant coursework?",
            "subtext": "Dean's List, scholarships, key projects - anything that stands out."
        }
    ],
    "life": [
        {
            "id": "xFactorCategory",
            "question": "Outside work and school, how do you spend your time?",
            "subtext": "Tell me about your main area of interest - sports, volunteering, creative arts, tech projects, travel, or something else?"
        },
        {
            "id": "xFactorDetail",
            "question": "Tell us about a specific achievement or role in that area.",
            "subtext": "What did you accomplish? What role did you play?"
        },
        {
            "id": "xFactorLessons",
            "question": "What valuable lessons did you learn?",
            "subtext": "How do these experiences connect to your goals?"
        }
    ],
    "skills": [
        {
            "id": "hardSkills",
            "question": "What are your top 5 tools or technical skills?",
            "subtext": "The software, languages, or technical abilities you use most."
        },
        {
            "id": "softSkillsFriend",
            "question": "How would your best friend describe you in three words?",
            "subtext": "Think about what they'd say about your personality."
        },
        {
            "id": "softSkillsSelf",
            "question": "How would you describe yourself in three words?"
        }
    ],
    "impact": [
        {
            "id": "legacyStatement",
            "question": "What impact do you want to make?",
            "subtext": "Think big - how do you want to change your industry, community, or the world?"
        },
        {
            "id": "socialLinks",
            "question": "Where else can people find you?",
            "subtext": "LinkedIn, GitHub, portfolio site, Instagram - any relevant URLs."
        }
    ]
}


class TokenRequest(BaseModel):
    room_name: str
    participant_name: str
    participant_identity: Optional[str] = None


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


@app.get("/")
async def root():
    return {
        "service": "MBIO Voice Agent API",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/api/token", response_model=TokenResponse)
async def generate_token(request: TokenRequest):
    """
    Generate a LiveKit access token for a participant to join a room.
    Also dispatches an agent to the room.
    """
    try:
        # Set token identity
        identity = request.participant_identity or request.participant_name
        
        # Create access token with fluent API (livekit-api >= 0.6.0)
        token = (
            api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            .with_identity(identity)
            .with_name(request.participant_name)
            .with_grants(api.VideoGrants(
                room_join=True,
                room=request.room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True
            ))
        )
        
        # Generate JWT
        jwt_token = token.to_jwt()
        
        # Create room with metadata (agent will auto-dispatch via LiveKit Cloud)
        try:
            lk_api = await get_livekit_api()
            await lk_api.room.create_room(
                api.CreateRoomRequest(
                    name=request.room_name,
                    metadata=json.dumps({
                        "participant_name": request.participant_name,
                        "created_at": datetime.now().isoformat()
                    })
                )
            )
            print(f"[INFO] Room created: {request.room_name}")
            # Note: Agent auto-dispatches via LiveKit Cloud - no manual dispatch needed
        except Exception as room_error:
            print(f"[WARN] Room creation note: {room_error}")
        
        return TokenResponse(
            token=jwt_token,
            url=LIVEKIT_URL,
            room_name=request.room_name
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate token: {str(e)}")


@app.get("/api/voice-questions", response_model=QuestionResponse)
async def get_voice_questions(phase: str, life_stage: Optional[str] = None):
    """
    Get questions for a specific phase of the voice interview.
    Optionally filter by life_stage for conditional questions.
    """
    phase_lower = phase.lower()
    
    if phase_lower not in VOICE_QUESTIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid phase. Valid phases: {list(VOICE_QUESTIONS.keys())}"
        )
    
    questions = VOICE_QUESTIONS[phase_lower]
    
    # Filter questions based on life_stage if provided
    if life_stage:
        filtered_questions = []
        for q in questions:
            conditional = q.get("conditional")
            if not conditional:
                filtered_questions.append(q)
            elif life_stage in conditional.get("values", []):
                filtered_questions.append(q)
        questions = filtered_questions
    
    return QuestionResponse(
        questions=questions,
        phase=phase_lower,
        total_questions=len(questions)
    )


@app.get("/api/voice-questions/all")
async def get_all_voice_questions(life_stage: Optional[str] = None):
    """
    Get all voice questions organized by phase.
    """
    result = {}
    phases_order = ["school", "life", "skills", "impact"]
    
    for phase in phases_order:
        questions = VOICE_QUESTIONS[phase]
        
        if life_stage:
            filtered_questions = []
            for q in questions:
                conditional = q.get("conditional")
                if not conditional:
                    filtered_questions.append(q)
                elif life_stage in conditional.get("values", []):
                    filtered_questions.append(q)
            questions = filtered_questions
        
        result[phase] = questions
    
    return {
        "phases": phases_order,
        "questions_by_phase": result,
        "total_questions": sum(len(q) for q in result.values())
    }


@app.post("/api/extract-profile")
async def extract_profile(request: ExtractProfileRequest):
    """
    Extract structured profile data from a conversation transcript.
    Uses the same extraction logic as the voice agent.
    """
    from agent_wrapper import extract_profile_from_transcript
    
    try:
        profile = extract_profile_from_transcript(request.transcript)
        return {
            "success": True,
            "profile": profile
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile extraction failed: {str(e)}")


class GenerateProfileRequest(BaseModel):
    basics_answers: dict
    transcript: list[dict]
    session_id: Optional[str] = None


@app.post("/api/generate-profile")
async def generate_profile_from_interview(request: GenerateProfileRequest):
    """
    Generate a complete profile from interview transcript using feature extraction.
    """
    from feature_extraction import extract_profile_features, convert_to_profile_format
    
    try:
        # Extract features from transcript
        extracted = extract_profile_features(
            transcript=request.transcript,
            basics_answers=request.basics_answers
        )
        
        # Convert to frontend profile format
        profile = convert_to_profile_format(extracted)
        
        return {
            "success": True,
            "profile": profile,
            "extracted_features": extracted
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile generation failed: {str(e)}")


@app.get("/api/sessions")
async def list_sessions():
    """
    List all saved interview sessions.
    """
    import glob
    from pathlib import Path
    
    output_dir = Path(__file__).parent.parent / "output"
    sessions = []
    
    for json_file in sorted(output_dir.glob("*.json"), reverse=True):
        try:
            with open(json_file) as f:
                data = json.load(f)
                sessions.append({
                    "session_id": data.get("session_id"),
                    "room_name": data.get("room_name"),
                    "timestamp": data.get("timestamp"),
                    "duration": data.get("duration", {}).get("formatted"),
                    "has_audio": data.get("audio_file") is not None,
                    "transcript_count": len(data.get("transcript", []))
                })
        except Exception as e:
            print(f"Error reading {json_file}: {e}")
    
    return {"sessions": sessions}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """
    Get a specific session's data including transcript and extracted profile.
    """
    from pathlib import Path
    
    output_dir = Path(__file__).parent.parent / "output"
    json_file = output_dir / f"{session_id}.json"
    
    if not json_file.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        with open(json_file) as f:
            data = json.load(f)
        
        # Check if audio file exists
        audio_file = output_dir / f"{session_id}.ogg"
        data["audio_available"] = audio_file.exists()
        
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading session: {str(e)}")


@app.get("/api/sessions/{session_id}/audio")
async def get_session_audio(session_id: str):
    """
    Get the audio file for a session.
    """
    from pathlib import Path
    from fastapi.responses import FileResponse
    
    output_dir = Path(__file__).parent.parent / "output"
    audio_file = output_dir / f"{session_id}.ogg"
    
    if not audio_file.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    return FileResponse(
        audio_file,
        media_type="audio/ogg",
        filename=f"{session_id}.ogg"
    )


class PrepareInterviewRequest(BaseModel):
    resume_data: dict
    life_stage: str  # "student" or "professional"
    user_name: str


@app.post("/api/prepare-interview")
async def prepare_interview(request: PrepareInterviewRequest):
    """
    Run the agentic pipeline to prepare a personalized voice interview.
    
    Takes parsed resume data and returns a complete interview briefing
    for the voice agent.
    
    Pipeline:
    1. Profile Analyzer - Identifies strengths, gaps, interesting hooks
    2. Question Planner - Creates personalized questions
    3. Interview Briefer - Generates voice agent context
    """
    from interview_prep import run_interview_prep_pipeline
    
    try:
        result = await run_interview_prep_pipeline(
            resume_data=request.resume_data,
            life_stage=request.life_stage,
            user_name=request.user_name
        )
        
        return {
            "success": True,
            "interview_briefing": result.get("interview_briefing"),
            "profile_analysis": result.get("profile_analysis"),
            "interview_plan": result.get("interview_plan"),
            "errors": result.get("errors", [])
        }
        
    except Exception as e:
        print(f"[ERROR] Interview preparation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to prepare interview: {str(e)}")


@app.post("/api/process-resume")
async def process_resume(
    file: UploadFile = File(...),
    linkedin_url: Optional[str] = Form(None)
):
    """
    Process a resume file (PDF or DOCX) and extract structured data using Gemini 3 Flash.
    
    Returns extracted profile data with gaps_to_explore for the voice interview.
    """
    from resume_parser import parse_resume, get_mime_type
    
    # Validate file type
    allowed_types = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword'
    ]
    
    # Get MIME type from content_type or filename
    mime_type = file.content_type
    if mime_type not in allowed_types:
        try:
            mime_type = get_mime_type(file.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    # Read file bytes
    file_bytes = await file.read()
    
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    
    if len(file_bytes) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB")
    
    try:
        # Parse resume with Gemini
        extracted_data = await parse_resume(
            file_bytes=file_bytes,
            mime_type=mime_type,
            filename=file.filename
        )
        
        # Add LinkedIn URL if provided
        if linkedin_url and linkedin_url.strip():
            if "basics" not in extracted_data:
                extracted_data["basics"] = {}
            if "profiles" not in extracted_data["basics"]:
                extracted_data["basics"]["profiles"] = []
            
            # Check if LinkedIn already exists
            linkedin_exists = any(
                p.get("network", "").lower() == "linkedin" 
                for p in extracted_data["basics"]["profiles"]
            )
            
            if not linkedin_exists:
                extracted_data["basics"]["profiles"].append({
                    "network": "LinkedIn",
                    "url": linkedin_url.strip()
                })
        
        return {
            "success": True,
            "data": extracted_data,
            "gaps_to_explore": extracted_data.get("_mbio", {}).get("gaps_to_explore", [])
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[ERROR] Resume processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process resume: {str(e)}")


@app.post("/api/process-resume-and-prepare")
async def process_resume_and_prepare_interview(
    file: UploadFile = File(...),
    life_stage: str = Form(...),
    linkedin_url: Optional[str] = Form(None)
):
    """
    Combined endpoint: Parse resume AND run the agentic interview prep pipeline.
    
    This is the full flow for preparing a personalized voice interview:
    1. Parse the resume with Gemini
    2. Run the 3-agent pipeline (Profile Analyzer -> Question Planner -> Interview Briefer)
    3. Return the complete interview briefing ready for the voice agent
    
    Use this endpoint when you want to go from resume upload directly to
    a prepared interview in one call.
    """
    from resume_parser import parse_resume, get_mime_type
    from interview_prep import run_interview_prep_pipeline
    
    # Validate file type
    allowed_types = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword'
    ]
    
    mime_type = file.content_type
    if mime_type not in allowed_types:
        try:
            mime_type = get_mime_type(file.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    # Validate life_stage
    if life_stage not in ["student", "professional"]:
        raise HTTPException(status_code=400, detail="life_stage must be 'student' or 'professional'")
    
    # Read file
    file_bytes = await file.read()
    
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB")
    
    try:
        # Step 1: Parse resume
        print(f"[INFO] Step 1: Parsing resume...")
        extracted_data = await parse_resume(
            file_bytes=file_bytes,
            mime_type=mime_type,
            filename=file.filename
        )
        
        # Add LinkedIn URL if provided
        if linkedin_url and linkedin_url.strip():
            if "basics" not in extracted_data:
                extracted_data["basics"] = {}
            if "profiles" not in extracted_data["basics"]:
                extracted_data["basics"]["profiles"] = []
            
            linkedin_exists = any(
                p.get("network", "").lower() == "linkedin" 
                for p in extracted_data["basics"]["profiles"]
            )
            
            if not linkedin_exists:
                extracted_data["basics"]["profiles"].append({
                    "network": "LinkedIn",
                    "url": linkedin_url.strip()
                })
        
        # Get user name from resume
        user_name = extracted_data.get("basics", {}).get("name", "Candidate")
        
        # Step 2: Run interview prep pipeline
        print(f"[INFO] Step 2: Running interview prep pipeline for {user_name}...")
        prep_result = await run_interview_prep_pipeline(
            resume_data=extracted_data,
            life_stage=life_stage,
            user_name=user_name
        )
        
        return {
            "success": True,
            "resume_data": extracted_data,
            "interview_briefing": prep_result.get("interview_briefing"),
            "profile_analysis": prep_result.get("profile_analysis"),
            "interview_plan": prep_result.get("interview_plan"),
            "pipeline_errors": prep_result.get("errors", [])
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[ERROR] Process and prepare failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process resume and prepare interview: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
