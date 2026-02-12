import json

from core.clients import get_openai_client


SIMPLE_EXTRACTION_PROMPT = """Extract structured profile information from this interview transcript.
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
Return valid JSON only, no additional text."""

DETAILED_EXTRACTION_PROMPT = """You are a profile data extractor. Analyze the interview transcript and extract structured profile information.

TRANSCRIPT:
{transcript}

BASICS ANSWERS (from form):
{basics}

Extract the following information into a JSON object. Only include fields that were explicitly mentioned.
Be thorough - extract ALL relevant information from the conversation.

Required structure:
{{
    "basics": {{
        "first_name": "string",
        "last_name": "string or null",
        "location": {{
            "city": "string or null",
            "state": "string or null",
            "country": "string or null"
        }},
        "headline": "A compelling professional headline based on their background",
        "mission_statement": "A 2-3 sentence introduction based on their goals and background"
    }},
    "experience": [
        {{
            "type": "internship|full-time|part-time|freelance|volunteer",
            "title": "string",
            "organization": {{
                "name": "string",
                "industry": "string or null"
            }},
            "start_date": "string or null",
            "end_date": "string or null",
            "description": "string",
            "bullets": ["achievement 1", "achievement 2"]
        }}
    ],
    "education": [
        {{
            "level": "high_school|associate|bachelor|master|phd|diploma|certificate",
            "degree": "string",
            "institution": "string",
            "year": "string or null",
            "details": "string - honors, coursework, GPA, etc."
        }}
    ],
    "skills": {{
        "hard_skills": ["skill1", "skill2"],
        "soft_skills": ["skill1", "skill2"],
        "tools": ["tool1", "tool2"]
    }},
    "extracurricular": [
        {{
            "type": "sports|clubs|volunteering|music_art|other",
            "title": "string",
            "organization": "string",
            "description": "string"
        }}
    ],
    "honors_awards": [
        {{
            "title": "string",
            "issuer": "string or null",
            "date": "string or null",
            "description": "string or null"
        }}
    ],
    "personality": {{
        "three_words_friend": ["word1", "word2", "word3"],
        "three_words_self": ["word1", "word2", "word3"]
    }},
    "goals": {{
        "primary_goal": "string",
        "impact_statement": "string"
    }},
    "social_links": [
        {{
            "platform": "LinkedIn|GitHub|Twitter|Instagram|Portfolio|Other",
            "url": "string"
        }}
    ]
}}

IMPORTANT:
- Generate compelling bullet points for experience (quantify achievements when possible)
- Create a professional headline that captures their unique value proposition
- Write a mission statement that tells their story
- Extract ALL skills mentioned (technical, soft skills, tools/software)
- Include ALL extracurricular activities (sports, clubs, volunteering, arts)
- Parse any URLs mentioned for social links

Return ONLY valid JSON, no additional text."""


def extract_profile_from_transcript(transcript: list[dict]) -> dict:
    if not transcript:
        return {}

    transcript_text = "\n".join(
        f"{item['role'].upper()}: {item['text']}"
        for item in transcript
        if item.get("text")
    )

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SIMPLE_EXTRACTION_PROMPT},
                {"role": "user", "content": transcript_text},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {}


def extract_profile_features(
    transcript: list[dict],
    basics_answers: dict,
    model: str = "gpt-4o",
) -> dict:
    if not transcript:
        return create_empty_profile(basics_answers)

    transcript_text = "\n".join(
        f"{'USER' if item['role'] == 'user' else 'INTERVIEWER'}: {item['text']}"
        for item in transcript
        if item.get("text")
    )

    prompt = DETAILED_EXTRACTION_PROMPT.format(
        transcript=transcript_text,
        basics=json.dumps(basics_answers, indent=2),
    )

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional profile data extractor. Extract structured data from interview transcripts.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        extracted = json.loads(response.choices[0].message.content)
        _merge_basics(extracted, basics_answers)
        return extracted
    except Exception:
        return create_empty_profile(basics_answers)


def create_empty_profile(basics_answers: dict) -> dict:
    profile = {
        "basics": {
            "first_name": "",
            "last_name": "",
            "location": {"city": "", "state": "", "country": ""},
            "headline": "",
            "mission_statement": "",
        },
        "experience": [],
        "education": [],
        "skills": {"hard_skills": [], "soft_skills": [], "tools": []},
        "extracurricular": [],
        "honors_awards": [],
        "personality": {"three_words_friend": [], "three_words_self": []},
        "goals": {"primary_goal": "", "impact_statement": ""},
        "social_links": [],
    }
    _merge_basics(profile, basics_answers)
    return profile


def convert_to_profile_format(extracted: dict) -> dict:
    basics = extracted.get("basics", {})
    skills = extracted.get("skills", {})
    personality = extracted.get("personality", {})
    goals = extracted.get("goals", {})

    full_name = basics.get("first_name", "")
    if basics.get("last_name"):
        full_name += " " + basics["last_name"]

    location_parts = []
    loc = basics.get("location", {})
    if loc.get("city"):
        location_parts.append(loc["city"])
    if loc.get("state"):
        location_parts.append(loc["state"])

    all_skills = skills.get("hard_skills", [])[:3] + skills.get("tools", [])[:2]

    sections = []
    for exp in extracted.get("experience", []):
        sections.append(
            {
                "id": f"exp-{len(sections)}",
                "type": "experience",
                "title": exp.get("title", "Experience"),
                "status": "expanded",
                "content": {
                    "role": exp.get("title", ""),
                    "organization": exp.get("organization", {}).get("name", ""),
                    "bullets": exp.get("bullets", []),
                },
            }
        )

    for edu in extracted.get("education", []):
        sections.append(
            {
                "id": f"edu-{len(sections)}",
                "type": "education",
                "title": edu.get("degree", "Education"),
                "status": "expanded",
                "content": {
                    "degree": edu.get("degree", ""),
                    "institution": edu.get("institution", ""),
                    "year": edu.get("year", ""),
                    "details": edu.get("details", ""),
                },
            }
        )

    for extra in extracted.get("extracurricular", []):
        sections.append(
            {
                "id": f"extra-{len(sections)}",
                "type": "extracurricular",
                "title": extra.get("title", "Activity"),
                "status": "expanded",
                "content": {
                    "role": extra.get("title", ""),
                    "organization": extra.get("organization", ""),
                    "details": extra.get("description", ""),
                },
            }
        )

    social_links = []
    for link in extracted.get("social_links", []):
        if isinstance(link, dict):
            social_links.append(
                {"platform": link.get("platform", "Link"), "url": link.get("url", "")}
            )
        elif isinstance(link, str):
            social_links.append({"platform": link, "url": ""})

    three_words = (
        personality.get("three_words_friend", [])[:2]
        + personality.get("three_words_self", [])[:1]
    )

    return {
        "meta": {
            "theme": "professional",
            "primary_color": "#25443c",
            "font_pairing": "serif",
        },
        "header": {
            "full_name": full_name,
            "headline": basics.get("headline", ""),
            "location": ", ".join(location_parts) if location_parts else "",
            "mission_statement": basics.get(
                "mission_statement", goals.get("impact_statement", "")
            ),
            "tags": all_skills[:5],
        },
        "sections": sections,
        "footer": {
            "social_links": social_links,
            "three_words": three_words[:3],
        },
    }


def _merge_basics(profile: dict, basics_answers: dict) -> None:
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
