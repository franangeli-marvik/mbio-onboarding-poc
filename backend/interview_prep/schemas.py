"""
Schemas for Interview Prep Pipeline

Defines the state and data structures used throughout the pipeline.
Following LangGraph 2026 best practices:
- Use TypedDict for state
- Keep state minimal and explicit
- Use Pydantic for data validation
"""

from typing import TypedDict, List, Optional, Literal
from pydantic import BaseModel, Field


# =============================================================================
# Pydantic Models for Structured Data (validated by LLM outputs)
# =============================================================================

class StrengthItem(BaseModel):
    """A strength identified from the resume with supporting evidence."""
    area: str = Field(description="The skill or strength area (e.g., 'backend_development', 'leadership')")
    evidence: List[str] = Field(description="Evidence from resume supporting this strength")
    confidence: Literal["high", "medium", "low"] = Field(default="medium")


class GapItem(BaseModel):
    """A gap or missing information that should be explored in the interview."""
    area: str = Field(description="The area where information is missing")
    reason: str = Field(description="Why this is important to explore")
    priority: Literal["high", "medium", "low"] = Field(default="medium")


class InterestingHook(BaseModel):
    """An interesting topic worth exploring deeper in the interview."""
    topic: str = Field(description="The interesting topic to explore")
    reason: str = Field(description="Why this is interesting")
    suggested_angle: Optional[str] = Field(default=None, description="Suggested angle for questions")


class TenantConfig(BaseModel):
    """Configuration for a specific recruiter/tenant."""
    tenant_id: str = Field(description="Unique identifier for the tenant")
    name: str = Field(description="Display name of the recruiter/agency")
    focus_area: str = Field(description="Primary focus (e.g., 'Technical Depth', 'Culture Fit', 'Sales Aggressiveness')")
    tone: Literal["formal", "casual", "direct", "supportive"] = Field(default="professional")
    custom_instructions: Optional[str] = Field(default=None, description="Specific instructions for the AI agent")

class SoftSkillItem(BaseModel):
    """Inferred soft skill with evidence."""
    skill: str = Field(description="The soft skill identified (e.g., 'Leadership', 'Communication')")
    evidence: str = Field(description="Behavioral evidence from resume actions")
    confidence: Literal["high", "medium", "low"] = Field(default="medium")

class ProfileAnalysis(BaseModel):
    """Output from Agent 1: Profile Analyzer."""
    life_stage: Literal["student", "professional"] = Field(description="Detected life stage")
    domain: str = Field(description="Detected professional domain (e.g., 'Software Engineering', 'Finance', 'Marketing')")
    profile_summary: str = Field(description="Brief summary of the candidate's profile")
    strengths: List[StrengthItem] = Field(default_factory=list)
    gaps: List[GapItem] = Field(default_factory=list)
    interesting_hooks: List[InterestingHook] = Field(default_factory=list)
    soft_skills_inference: List[SoftSkillItem] = Field(default_factory=list, description="Inferred soft skills")
    key_experiences: List[str] = Field(default_factory=list, description="Key experiences to reference")
    avoid_topics: List[str] = Field(default_factory=list, description="Topics already well-covered in resume")


class QuestionItem(BaseModel):
    """A question to ask during the interview."""
    id: str | int = Field(description="Unique question identifier")
    question: str = Field(description="The question to ask")
    intent: str = Field(description="What we want to learn from this question")
    priority: str = Field(default="recommended", description="Question priority level")
    follow_up_if: Optional[str] = Field(default=None, description="Condition to ask follow-up")
    follow_up_question: Optional[str] = Field(default=None, description="Follow-up question if condition met")
    context_from_resume: Optional[str] = Field(default=None, description="Resume context to reference")
    
    @property
    def id_str(self) -> str:
        """Get id as string."""
        return str(self.id)


class InterviewPhase(BaseModel):
    """A phase of the interview with its questions."""
    phase_name: str = Field(description="Name of the phase (e.g., 'warmup', 'deep_dive')")
    phase_goal: str = Field(description="What this phase aims to achieve")
    estimated_duration: str = Field(description="Estimated duration (e.g., '2-3 min')")
    questions: List[QuestionItem] = Field(default_factory=list)


class InterviewPlan(BaseModel):
    """Output from Agent 2: Question Planner."""
    total_estimated_duration: str = Field(description="Total estimated interview duration")
    phases: List[InterviewPhase] = Field(default_factory=list)
    adaptive_notes: List[str] = Field(default_factory=list, description="Notes on how to adapt")


class InterviewBriefing(BaseModel):
    """Output from Agent 3: Interview Briefer - ready for voice agent."""
    candidate_context: str = Field(description="Context summary for the voice agent")
    conversation_guidelines: str | dict = Field(description="How to conduct the conversation")
    questions_script: List[dict] = Field(description="Ordered list of questions with notes")
    topics_to_avoid: List[str] = Field(default_factory=list, description="Topics to skip")
    personalization_hints: List[str] = Field(default_factory=list, description="Ways to personalize")
    
    @property
    def guidelines_text(self) -> str:
        """Get conversation_guidelines as text."""
        if isinstance(self.conversation_guidelines, str):
            return self.conversation_guidelines
        elif isinstance(self.conversation_guidelines, dict):
            # Convert dict to readable text
            parts = []
            for key, value in self.conversation_guidelines.items():
                parts.append(f"{key}: {value}")
            return "\n".join(parts)
        return str(self.conversation_guidelines)


# =============================================================================
# LangGraph State (TypedDict following 2026 best practices)
# =============================================================================

class InterviewPrepState(TypedDict):
    """
    State for the Interview Prep Pipeline.
    
    Following LangGraph best practices:
    - Minimal state with only necessary fields
    - Each node returns partial updates
    - No mutation of state objects
    """
    # Input
    resume_data: dict  # Parsed resume JSON from resume_parser
    life_stage: str    # "student" or "professional"
    user_name: str     # Candidate's name for personalization
    tenant_config: Optional[dict] # TenantConfig dict
    
    # Agent 1 Output
    profile_analysis: Optional[dict]  # ProfileAnalysis as dict
    
    # Agent 2 Output  
    interview_plan: Optional[dict]    # InterviewPlan as dict
    
    # Agent 3 Output (Final)
    interview_briefing: Optional[dict]  # InterviewBriefing as dict
    
    # Metadata
    errors: List[str]  # Any errors encountered
