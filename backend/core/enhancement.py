import json
import logging

from core.clients import get_gemini_client
from core.extraction import convert_to_profile_format
from agent.prompt_manager import get_prompt, get_langfuse_prompt
from observability.tracing import traced_generation

logger = logging.getLogger(__name__)

MODEL = "gemini-2.0-flash"

_FALLBACK_ENHANCER_SYSTEM = """\
You are an expert resume enhancer for M.bio.

You receive two inputs:
1. A parsed resume (original data from the uploaded PDF/DOCX).
2. A voice interview transcript where the candidate elaborated on their experiences.

Your task is to produce an ENHANCED version of the resume that merges both sources.

Rules:
- Keep every fact from the original resume intact.
- Enrich experience bullet points with concrete details, metrics, and context the candidate shared during the interview.
- Add new experiences, skills, or achievements that were mentioned ONLY in the interview but are missing from the resume.
- Improve the headline and summary/mission statement using insights from the interview.
- Add soft skills and personality traits revealed during the interview.
- Do NOT fabricate information. Only use what the candidate actually said.
- Preserve chronological order of experiences.
- Write in professional third-person resume language (not conversational).
- Quantify achievements whenever the candidate provided numbers.

Output a JSON object with this exact structure:
{
    "basics": {
        "first_name": "string",
        "last_name": "string or null",
        "location": {"city": "string", "state": "string", "country": "string"},
        "headline": "Enhanced professional headline",
        "mission_statement": "Enhanced 2-3 sentence introduction"
    },
    "experience": [
        {
            "type": "internship|full-time|part-time|freelance|volunteer",
            "title": "string",
            "organization": {"name": "string", "industry": "string or null"},
            "start_date": "string or null",
            "end_date": "string or null",
            "description": "string",
            "bullets": ["enhanced bullet 1", "enhanced bullet 2"]
        }
    ],
    "education": [
        {
            "level": "string",
            "degree": "string",
            "institution": "string",
            "year": "string or null",
            "details": "string"
        }
    ],
    "skills": {
        "hard_skills": [],
        "soft_skills": [],
        "tools": []
    },
    "extracurricular": [
        {
            "type": "string",
            "title": "string",
            "organization": "string",
            "description": "string"
        }
    ],
    "honors_awards": [],
    "personality": {
        "three_words_friend": [],
        "three_words_self": []
    },
    "goals": {
        "primary_goal": "string",
        "impact_statement": "string"
    },
    "social_links": []
}

Return ONLY valid JSON."""

_FALLBACK_ENHANCER_USER = """\
ORIGINAL RESUME DATA:
```json
{{resume_json}}
```

INTERVIEW TRANSCRIPT:
{{transcript_text}}

PROFILE ANALYSIS (from pipeline):
```json
{{analysis_json}}
```

Candidate name: {{user_name}}

Merge the resume data with the interview insights to produce the enhanced JSON resume."""


def convert_resume_to_profile(resume_data: dict) -> dict:
    basics = resume_data.get("basics", {})

    full_name = basics.get("name", "")
    location_parts = []
    loc = basics.get("location", {})
    if isinstance(loc, dict):
        for key in ("city", "region", "country"):
            if loc.get(key):
                location_parts.append(loc[key])
    elif isinstance(loc, str):
        location_parts.append(loc)

    profiles = basics.get("profiles", [])
    social_links = [
        {"platform": p.get("network", "Link"), "url": p.get("url", "")}
        for p in profiles
        if p.get("url")
    ]

    tags = []
    for skill_group in resume_data.get("skills", []):
        if isinstance(skill_group, dict):
            tags.extend(skill_group.get("keywords", [])[:3])
        elif isinstance(skill_group, str):
            tags.append(skill_group)
    tags = tags[:5]

    sections = []
    for work in resume_data.get("work", []):
        sections.append({
            "id": f"exp-{len(sections)}",
            "type": "experience",
            "title": work.get("position", "Experience"),
            "status": "expanded",
            "content": {
                "role": work.get("position", ""),
                "organization": work.get("company", ""),
                "bullets": work.get("highlights", []),
            },
        })

    for edu in resume_data.get("education", []):
        degree = edu.get("studyType", "")
        if edu.get("area"):
            degree = f"{degree} in {edu['area']}" if degree else edu["area"]
        sections.append({
            "id": f"edu-{len(sections)}",
            "type": "education",
            "title": degree or "Education",
            "status": "expanded",
            "content": {
                "degree": degree,
                "institution": edu.get("institution", ""),
                "year": edu.get("endDate", edu.get("startDate", "")),
                "details": "",
            },
        })

    return {
        "meta": {
            "theme": "professional",
            "primary_color": "#6b7280",
            "font_pairing": "serif",
        },
        "header": {
            "full_name": full_name,
            "headline": basics.get("label", basics.get("summary", "")[:80] if basics.get("summary") else ""),
            "location": ", ".join(location_parts),
            "mission_statement": basics.get("summary", ""),
            "tags": tags,
        },
        "sections": sections,
        "footer": {
            "social_links": social_links,
            "three_words": [],
        },
    }


def enhance_resume(
    resume_data: dict,
    transcript: list[dict],
    profile_analysis: dict | None,
    basics_answers: dict | None,
) -> dict:
    resume_json = json.dumps(resume_data, indent=2, ensure_ascii=False)

    transcript_text = "\n".join(
        f"{'USER' if item.get('role') == 'user' else 'INTERVIEWER'}: {item.get('text', '')}"
        for item in transcript
        if item.get("text")
    )

    analysis_json = json.dumps(profile_analysis or {}, indent=2, ensure_ascii=False)

    user_name = "Candidate"
    if basics_answers and basics_answers.get("name"):
        user_name = basics_answers["name"]
    elif resume_data.get("basics", {}).get("name"):
        user_name = resume_data["basics"]["name"]

    system_prompt = get_prompt(
        "pipeline/resume-enhancer-system",
        fallback=_FALLBACK_ENHANCER_SYSTEM,
    )

    user_prompt = get_prompt(
        "pipeline/resume-enhancer-user",
        fallback=_FALLBACK_ENHANCER_USER,
        resume_json=resume_json,
        transcript_text=transcript_text,
        analysis_json=analysis_json,
        user_name=user_name,
    )

    lf_prompt = get_langfuse_prompt("pipeline/resume-enhancer-system")

    with traced_generation(
        "resume_enhancer",
        model=MODEL,
        prompt=lf_prompt,
        input_data={"system": system_prompt[:500], "user": user_prompt[:2000]},
    ) as gen:
        client = get_gemini_client()
        contents = [
            {"role": "user", "parts": [{"text": system_prompt}]},
            {"role": "model", "parts": [{"text": "I understand. I will merge the resume with interview insights and return enhanced JSON."}]},
            {"role": "user", "parts": [{"text": user_prompt}]},
        ]

        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config={"temperature": 0.3, "response_mime_type": "application/json"},
        )

        usage = getattr(response, "usage_metadata", None)
        gen.update(
            output=response.text,
            usage_details={
                "input": getattr(usage, "prompt_token_count", 0),
                "output": getattr(usage, "candidates_token_count", 0),
            } if usage else None,
        )

    enhanced_extracted = json.loads(response.text)

    if basics_answers:
        _merge_basics_into(enhanced_extracted, basics_answers)

    return convert_to_profile_format(enhanced_extracted)


def _merge_basics_into(profile: dict, basics_answers: dict) -> None:
    if basics_answers.get("name"):
        names = basics_answers["name"].split()
        profile.setdefault("basics", {})
        profile["basics"]["first_name"] = names[0]
        if len(names) > 1:
            profile["basics"]["last_name"] = " ".join(names[1:])

    if basics_answers.get("location"):
        profile.setdefault("basics", {})
        profile["basics"].setdefault("location", {})
        loc_parts = basics_answers["location"].split(",")
        if len(loc_parts) >= 2:
            profile["basics"]["location"]["city"] = loc_parts[0].strip()
            profile["basics"]["location"]["state"] = loc_parts[-1].strip()
        else:
            profile["basics"]["location"]["city"] = basics_answers["location"]
