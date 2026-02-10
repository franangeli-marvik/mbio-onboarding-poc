import json
from datetime import datetime

from google.genai import types

from core.clients import get_gemini_client


RESUME_SCHEMA = {
    "type": "object",
    "properties": {
        "basics": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "location": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"},
                        "region": {"type": "string"},
                        "country": {"type": "string"},
                    },
                },
                "summary": {"type": "string"},
                "profiles": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "network": {"type": "string"},
                            "url": {"type": "string"},
                        },
                    },
                },
            },
        },
        "work": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "position": {"type": "string"},
                    "location": {"type": "string"},
                    "startDate": {"type": "string"},
                    "endDate": {"type": "string"},
                    "summary": {"type": "string"},
                    "highlights": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "institution": {"type": "string"},
                    "area": {"type": "string"},
                    "studyType": {"type": "string"},
                    "minor": {"type": "string"},
                    "location": {"type": "string"},
                    "startDate": {"type": "string"},
                    "endDate": {"type": "string"},
                    "score": {"type": "string"},
                    "courses": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "technologies": {"type": "array", "items": {"type": "string"}},
                    "highlights": {"type": "array", "items": {"type": "string"}},
                    "url": {"type": "string"},
                },
            },
        },
        "awards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "date": {"type": "string"},
                    "awarder": {"type": "string"},
                    "summary": {"type": "string"},
                },
            },
        },
        "certificates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "date": {"type": "string"},
                    "issuer": {"type": "string"},
                    "url": {"type": "string"},
                },
            },
        },
        "languages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "language": {"type": "string"},
                    "fluency": {"type": "string"},
                },
            },
        },
        "volunteer": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "position": {"type": "string"},
                    "startDate": {"type": "string"},
                    "endDate": {"type": "string"},
                    "summary": {"type": "string"},
                    "highlights": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "interests": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}

EXTRACTION_PROMPT = """Parse this resume into JSON with these exact top-level keys:
- basics: {name, email, phone, location: {city, region, country}, summary, profiles: [{network, url}]}
- work: [{company, position, location, startDate (YYYY-MM), endDate, summary, highlights: [str]}]
- education: [{institution, area, studyType, location, startDate, endDate}]
- skills: [{category, keywords: [str]}]
- languages: [{language, fluency}]
- awards: [{title, date, awarder, summary}]
- publications: [{name, summary}]
Dates as YYYY-MM. Empty arrays for missing sections. No extra keys."""


def parse_resume(file_bytes: bytes, mime_type: str, filename: str = "resume") -> dict:
    client = get_gemini_client()

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
            EXTRACTION_PROMPT,
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )

    extracted_data = json.loads(response.text)
    gaps = generate_gaps_to_explore(extracted_data)

    return {
        **extracted_data,
        "_mbio": {
            "gaps_to_explore": gaps,
            "source": "resume_upload",
            "source_filename": filename,
            "source_mime_type": mime_type,
            "parsed_at": datetime.now().isoformat(),
            "model": "gemini-2.0-flash",
        },
    }


def generate_gaps_to_explore(extracted_data: dict) -> list[str]:
    gaps = [
        "What are your career goals and what are you working toward right now?",
        "What impact do you want to make in your industry or community?",
        "How would your friends or colleagues describe you in three words?",
    ]

    if not extracted_data.get("basics", {}).get("summary"):
        gaps.append(
            "Can you give me a brief introduction about yourself and your professional journey?"
        )

    if extracted_data.get("work"):
        gaps.append(
            "Of all your professional experiences, what achievement are you most proud of and why?"
        )

    if not extracted_data.get("interests"):
        gaps.append("What do you enjoy doing outside of work? Any hobbies or interests?")

    if not extracted_data.get("volunteer"):
        gaps.append("Have you been involved in any volunteer work or community activities?")

    if extracted_data.get("projects"):
        gaps.append("What motivated you to work on your personal projects?")

    gaps.append("What's something new you're learning or want to learn?")
    return gaps


def get_mime_type(filename: str) -> str:
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        return "application/pdf"
    if lower_name.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if lower_name.endswith(".doc"):
        return "application/msword"
    raise ValueError(
        f"Unsupported file type: {filename}. Please upload a PDF or Word document."
    )
