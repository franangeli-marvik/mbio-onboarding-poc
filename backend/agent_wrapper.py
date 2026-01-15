"""
Agent Wrapper for MBIO Voice Agent
Adapts the original agent.py for use with FastAPI and the frontend voice UI.
"""

import json
import os
import asyncio
from datetime import datetime
from typing import Optional, Callable
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# OpenAI client for profile extraction
openai_client = OpenAI()

# Model configuration
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai").lower()

# Extraction prompt for post-conversation profile extraction
EXTRACTION_PROMPT = """
Extract structured profile information from this interview transcript.
Return a JSON object with these fields:
- first_name: User's first name
- last_name: User's last name (if mentioned)
- location: City/Country where they're from
- career_goals: What they want to achieve professionally
- achievements: List of their accomplishments mentioned
- skills: Technical and soft skills mentioned
- personality_traits: How they describe themselves
- education: Their educational background
- social_links: Any URLs or social profiles mentioned

Only include fields that were explicitly mentioned in the conversation.
Return valid JSON only, no additional text.
"""

# Agent instruction for voice interviews
VOICE_AGENT_INSTRUCTION = """
You are a friendly interviewer for MBIO helping users build their professional profile.

You are conducting a structured interview with specific questions to ask.
The frontend will tell you which question to ask next.

Guidelines:
- Be warm, encouraging, and conversational
- Ask ONE question at a time as directed by the system
- Listen actively and acknowledge what the user shares
- Keep responses concise - this is a voice conversation
- If the user's answer is unclear, ask a brief follow-up
- When you receive a "move_to_next" signal, transition smoothly to the next question

Current interview phases: SCHOOL → LIFE → SKILLS → IMPACT
"""

# Prompts for each phase transition
PHASE_TRANSITIONS = {
    "school": "Great! Now let's talk about your education and career experience.",
    "life": "Wonderful! Now I'd love to hear about what you do outside of work and school.",
    "skills": "Excellent! Let's discuss your skills and how others see you.",
    "impact": "Almost done! Let's talk about the impact you want to make."
}


def extract_profile_from_transcript(transcript: list[dict]) -> dict:
    """
    Extract structured profile data from a conversation transcript.
    
    Args:
        transcript: List of {"role": "user"|"agent", "text": "...", "timestamp": ...}
    
    Returns:
        Dictionary with extracted profile fields
    """
    if not transcript:
        return {}
    
    # Format transcript for extraction
    transcript_text = "\n".join([
        f"{item['role'].upper()}: {item['text']}" 
        for item in transcript
        if item.get('text')
    ])
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": transcript_text}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[WARN] Error en extracción: {e}")
        return {}


def get_realtime_model_config() -> dict:
    """
    Get the configuration for the realtime model based on environment.
    """
    if MODEL_PROVIDER == "gemini":
        return {
            "provider": "gemini",
            "model": "gemini-live-2.5-flash-native-audio",
            "voice": "Puck",
            "temperature": 0.8,
            "project": os.getenv("GOOGLE_CLOUD_PROJECT", "mbio-profile-creation"),
            "location": os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        }
    else:
        return {
            "provider": "openai",
            "model": "gpt-4o-realtime-preview",
            "voice": "alloy",
            "modalities": ["audio", "text"]
        }


def create_question_prompt(question: dict, phase: str, is_first_in_phase: bool = False) -> str:
    """
    Create a prompt for the agent to ask a specific question.
    
    Args:
        question: Question object with id, question, subtext
        phase: Current phase (school, life, skills, impact)
        is_first_in_phase: Whether this is the first question in the phase
    
    Returns:
        Formatted prompt string for the agent
    """
    prompt_parts = []
    
    # Add phase transition if first question
    if is_first_in_phase and phase in PHASE_TRANSITIONS:
        prompt_parts.append(PHASE_TRANSITIONS[phase])
    
    # Add the main question
    prompt_parts.append(f"Ask the user: \"{question['question']}\"")
    
    # Add subtext context if available
    if question.get('subtext'):
        prompt_parts.append(f"Context for you (don't read this verbatim): {question['subtext']}")
    
    return "\n".join(prompt_parts)


def format_answers_for_profile(
    basics_answers: dict,
    voice_transcript: list[dict]
) -> dict:
    """
    Combine keyboard answers from BASICS phase with extracted voice answers.
    
    Args:
        basics_answers: Answers from the keyboard input phase (name, location, lifeStage, primaryGoal)
        voice_transcript: Full transcript from the voice interview
    
    Returns:
        Combined answers dictionary ready for profile generation
    """
    # Start with basics
    combined = {**basics_answers}
    
    # Extract structured data from voice transcript
    extracted = extract_profile_from_transcript(voice_transcript)
    
    # Map extracted fields to expected answer format
    field_mapping = {
        "education": "major",
        "achievements": "bigWin",
        "skills": "hardSkills",
        "personality_traits": "softSkillsSelf",
        "career_goals": "legacyStatement",
        "social_links": "socialLinks"
    }
    
    for extracted_field, answer_field in field_mapping.items():
        if extracted_field in extracted and extracted[extracted_field]:
            value = extracted[extracted_field]
            # Convert lists to comma-separated strings
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            combined[answer_field] = value
    
    return combined


class VoiceInterviewSession:
    """
    Manages a voice interview session state.
    """
    
    def __init__(self, session_id: str, basics_answers: dict):
        self.session_id = session_id
        self.basics_answers = basics_answers
        self.life_stage = basics_answers.get("lifeStage", "student")
        self.current_phase = "school"
        self.current_question_index = 0
        self.transcript: list[dict] = []
        self.answers: dict = {}
        self.started_at = datetime.now()
        self.phases = ["school", "life", "skills", "impact"]
    
    def add_to_transcript(self, role: str, text: str):
        """Add a message to the transcript."""
        self.transcript.append({
            "role": role,
            "text": text,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_current_question(self, questions_by_phase: dict) -> Optional[dict]:
        """Get the current question based on phase and index."""
        phase_questions = questions_by_phase.get(self.current_phase, [])
        if self.current_question_index < len(phase_questions):
            return phase_questions[self.current_question_index]
        return None
    
    def advance_to_next_question(self, questions_by_phase: dict) -> tuple[Optional[dict], bool]:
        """
        Advance to the next question.
        
        Returns:
            Tuple of (next_question, is_interview_complete)
        """
        phase_questions = questions_by_phase.get(self.current_phase, [])
        self.current_question_index += 1
        
        # Check if we need to move to next phase
        if self.current_question_index >= len(phase_questions):
            current_phase_index = self.phases.index(self.current_phase)
            
            if current_phase_index < len(self.phases) - 1:
                # Move to next phase
                self.current_phase = self.phases[current_phase_index + 1]
                self.current_question_index = 0
            else:
                # Interview complete
                return None, True
        
        return self.get_current_question(questions_by_phase), False
    
    def is_first_question_in_phase(self) -> bool:
        """Check if current question is the first in its phase."""
        return self.current_question_index == 0
    
    def get_progress(self, questions_by_phase: dict) -> dict:
        """Get current progress information."""
        total_questions = sum(len(q) for q in questions_by_phase.values())
        
        # Count completed questions
        completed = 0
        for i, phase in enumerate(self.phases):
            if phase == self.current_phase:
                completed += self.current_question_index
                break
            else:
                completed += len(questions_by_phase.get(phase, []))
        
        return {
            "current_phase": self.current_phase,
            "current_question_index": self.current_question_index,
            "total_questions": total_questions,
            "completed_questions": completed,
            "progress_percent": round((completed / total_questions) * 100) if total_questions > 0 else 0
        }
    
    def get_final_profile_data(self) -> dict:
        """Get combined data for profile generation."""
        return format_answers_for_profile(self.basics_answers, self.transcript)


# In-memory session storage (for development)
# In production, use Redis or similar
_sessions: dict[str, VoiceInterviewSession] = {}


def create_session(session_id: str, basics_answers: dict) -> VoiceInterviewSession:
    """Create a new voice interview session."""
    session = VoiceInterviewSession(session_id, basics_answers)
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> Optional[VoiceInterviewSession]:
    """Get an existing session by ID."""
    return _sessions.get(session_id)


def delete_session(session_id: str):
    """Delete a session."""
    if session_id in _sessions:
        del _sessions[session_id]
