from typing import TypedDict, List, Optional, Literal

from pydantic import BaseModel, Field, field_validator


class StrengthItem(BaseModel):
    area: str = Field(description="The skill or strength area")
    evidence: List[str] = Field(description="Evidence from resume supporting this strength")
    confidence: Literal["high", "medium", "low"] = Field(default="medium")


class GapItem(BaseModel):
    area: str = Field(description="The area where information is missing")
    reason: str = Field(description="Why this is important to explore")
    priority: Literal["high", "medium", "low"] = Field(default="medium")


class InterestingHook(BaseModel):
    topic: str = Field(description="The interesting topic to explore")
    reason: str = Field(description="Why this is interesting")
    suggested_angle: Optional[str] = Field(default=None)


class PositionConfig(BaseModel):
    id: str
    title: str
    focus_area: str
    custom_instructions: str | None = None


class TenantConfig(BaseModel):
    tenant_id: str
    company_name: str
    tone: Literal["formal", "casual", "direct", "supportive"] = Field(default="supportive")
    positions: list[PositionConfig] = Field(default_factory=list)


class SoftSkillItem(BaseModel):
    skill: str
    evidence: str
    confidence: Literal["high", "medium", "low"] = Field(default="medium")


class ProfileAnalysis(BaseModel):
    life_stage: Literal["student", "professional"]
    domain: str = Field(description="Detected professional domain")
    profile_summary: str
    strengths: List[StrengthItem] = Field(default_factory=list)
    gaps: List[GapItem] = Field(default_factory=list)
    interesting_hooks: List[InterestingHook] = Field(default_factory=list)
    soft_skills_inference: List[SoftSkillItem] = Field(default_factory=list)
    key_experiences: List[str] = Field(default_factory=list)
    avoid_topics: List[str] = Field(default_factory=list)

    @field_validator("key_experiences", "avoid_topics", mode="before")
    @classmethod
    def coerce_to_strings(cls, v):
        if not isinstance(v, list):
            return v
        return [str(item) if not isinstance(item, str) else item for item in v]


class QuestionItem(BaseModel):
    id: str | int
    question: str
    intent: str
    priority: str = Field(default="recommended")
    follow_up_if: Optional[str] = Field(default=None)
    follow_up_question: Optional[str] = Field(default=None)
    context_from_resume: Optional[str | bool] = Field(default=None)

    @field_validator("context_from_resume", mode="before")
    @classmethod
    def coerce_context(cls, v):
        if isinstance(v, bool):
            return str(v).lower()
        return v

    @property
    def id_str(self) -> str:
        return str(self.id)


class InterviewPhase(BaseModel):
    phase_name: str
    phase_goal: str
    estimated_duration: str
    questions: List[QuestionItem] = Field(default_factory=list)


class InterviewPlan(BaseModel):
    total_estimated_duration: str
    phases: List[InterviewPhase] = Field(default_factory=list)
    adaptive_notes: List[str] = Field(default_factory=list)


class InterviewBriefing(BaseModel):
    candidate_context: str
    conversation_guidelines: str | dict
    questions_script: List[dict]
    topics_to_avoid: List[str] = Field(default_factory=list)
    personalization_hints: List[str] = Field(default_factory=list)

    @property
    def guidelines_text(self) -> str:
        if isinstance(self.conversation_guidelines, str):
            return self.conversation_guidelines
        if isinstance(self.conversation_guidelines, dict):
            return "\n".join(f"{k}: {v}" for k, v in self.conversation_guidelines.items())
        return str(self.conversation_guidelines)


class InterviewPrepState(TypedDict):
    resume_data: dict
    life_stage: str
    user_name: str
    tenant_config: Optional[dict]
    profile_analysis: Optional[dict]
    interview_plan: Optional[dict]
    interview_briefing: Optional[dict]
    errors: List[str]
