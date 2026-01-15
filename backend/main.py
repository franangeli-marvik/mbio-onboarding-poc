"""
FastAPI Backend for MBIO Voice Agent
Provides endpoints for LiveKit token generation and voice interview orchestration.
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from livekit import api
from livekit.api import LiveKitAPI
from dotenv import load_dotenv

load_dotenv()

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

# LiveKit configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")

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
        
        # Explicitly dispatch agent to the room
        # This is needed because LiveKit Cloud auto-dispatch may not be configured
        try:
            lk_api = await get_livekit_api()
            
            # Create room first (if it doesn't exist)
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
            
            # Dispatch agent to the room
            dispatch_request = api.CreateAgentDispatchRequest(
                room=request.room_name,
                metadata=json.dumps({
                    "participant_name": request.participant_name
                })
            )
            await lk_api.agent_dispatch.create_dispatch(dispatch_request)
            print(f"[INFO] Agent dispatched to room: {request.room_name}")
            
        except Exception as dispatch_error:
            # Log but don't fail - the user can still join, agent may auto-join later
            print(f"[WARN] Agent dispatch failed (may be auto-dispatched): {dispatch_error}")
        
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
