"""
Resume Parser Module for MBIO Profile Creation
Extracts structured data from PDF/DOCX resumes using Gemini 3 Flash.
"""

import os
import json
from datetime import datetime
from typing import Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Initialize Gemini client
# Uses GOOGLE_API_KEY env var or Application Default Credentials
def get_genai_client():
    """Get Google GenAI client with proper authentication."""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key)
    else:
        # Use Application Default Credentials (for GCP)
        return genai.Client()


# JSON Schema for resume extraction (based on JSON Resume standard + M.bio extensions)
RESUME_SCHEMA = {
    "type": "object",
    "properties": {
        "basics": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Full name of the candidate"},
                "email": {"type": "string", "description": "Email address"},
                "phone": {"type": "string", "description": "Phone number"},
                "location": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"},
                        "region": {"type": "string", "description": "State or province"},
                        "country": {"type": "string"}
                    }
                },
                "summary": {"type": "string", "description": "Professional summary or objective"},
                "profiles": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "network": {"type": "string", "description": "Platform name (LinkedIn, GitHub, etc.)"},
                            "url": {"type": "string", "description": "Profile URL"}
                        }
                    }
                }
            }
        },
        "work": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Company or organization name"},
                    "position": {"type": "string", "description": "Job title"},
                    "location": {"type": "string", "description": "Job location"},
                    "startDate": {"type": "string", "description": "Start date (YYYY-MM format)"},
                    "endDate": {"type": "string", "description": "End date or null if current"},
                    "summary": {"type": "string", "description": "Brief role description"},
                    "highlights": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key achievements as bullet points"
                    }
                }
            }
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "institution": {"type": "string", "description": "School or university name"},
                    "area": {"type": "string", "description": "Field of study or major"},
                    "studyType": {"type": "string", "description": "Degree type (Bachelor, Master, etc.)"},
                    "minor": {"type": "string", "description": "Minor if applicable"},
                    "location": {"type": "string"},
                    "startDate": {"type": "string"},
                    "endDate": {"type": "string"},
                    "score": {"type": "string", "description": "GPA or honors"},
                    "courses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Relevant courses"
                    }
                }
            }
        },
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Skill category (Languages, Frameworks, Tools, etc.)"},
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of skills in this category"
                    }
                }
            }
        },
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "technologies": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "highlights": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "url": {"type": "string"}
                }
            }
        },
        "awards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "date": {"type": "string"},
                    "awarder": {"type": "string"},
                    "summary": {"type": "string"}
                }
            }
        },
        "certificates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "date": {"type": "string"},
                    "issuer": {"type": "string"},
                    "url": {"type": "string"}
                }
            }
        },
        "languages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "language": {"type": "string"},
                    "fluency": {"type": "string"}
                }
            }
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
                    "highlights": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
        },
        "interests": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
        }
    }
}

# Prompt for resume extraction
EXTRACTION_PROMPT = """
You are an expert resume parser. Extract ALL information from this resume into the specified JSON schema.

IMPORTANT GUIDELINES:
1. Extract EVERY piece of information you can find
2. For work experience, convert bullet points into the "highlights" array
3. Categorize skills into logical groups (Languages, Frameworks, Tools, Soft Skills, etc.)
4. Parse dates into YYYY-MM format when possible
5. Extract social profiles (LinkedIn, GitHub, Portfolio, etc.) into basics.profiles
6. If information is not present, use null or empty arrays
7. Be thorough - don't miss any details

Return ONLY valid JSON matching the schema. No additional text.
"""


async def parse_resume(file_bytes: bytes, mime_type: str, filename: str = "resume") -> dict:
    """
    Parse a resume file using Gemini 3 Flash.
    
    Args:
        file_bytes: The raw bytes of the file
        mime_type: MIME type (application/pdf or application/vnd.openxmlformats-officedocument.wordprocessingml.document)
        filename: Original filename for logging
    
    Returns:
        Dictionary with extracted data and M.bio metadata
    """
    client = get_genai_client()
    
    print(f"[INFO] Parsing resume: {filename} ({mime_type})")
    
    try:
        # Send file directly to Gemini 3 Flash
        response = await client.aio.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                EXTRACTION_PROMPT
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,  # Low temperature for consistent extraction
                response_mime_type="application/json",
            )
        )
        
        # Parse the JSON response
        extracted_data = json.loads(response.text)
        
        # Generate gaps to explore (what the interview should focus on)
        gaps = generate_gaps_to_explore(extracted_data)
        
        # Add M.bio metadata
        result = {
            **extracted_data,
            "_mbio": {
                "gaps_to_explore": gaps,
                "source": "resume_upload",
                "source_filename": filename,
                "source_mime_type": mime_type,
                "parsed_at": datetime.now().isoformat(),
                "model": "gemini-3-flash-preview"
            }
        }
        
        print(f"[INFO] Successfully parsed resume. Found {len(extracted_data.get('work', []))} work experiences, {len(extracted_data.get('education', []))} education entries")
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse Gemini response as JSON: {e}")
        raise ValueError(f"Failed to parse resume: Invalid JSON response from AI model")
    except Exception as e:
        print(f"[ERROR] Resume parsing failed: {e}")
        raise


def generate_gaps_to_explore(extracted_data: dict) -> list[str]:
    """
    Analyze extracted data and identify what information is missing
    that the voice interview should explore.
    """
    gaps = []
    
    basics = extracted_data.get("basics", {})
    work = extracted_data.get("work", [])
    education = extracted_data.get("education", [])
    skills = extracted_data.get("skills", [])
    projects = extracted_data.get("projects", [])
    volunteer = extracted_data.get("volunteer", [])
    interests = extracted_data.get("interests", [])
    
    # Always ask about career goals (never in resume)
    gaps.append("What are your career goals and what are you working toward right now?")
    
    # Always ask about impact (rarely in resume)
    gaps.append("What impact do you want to make in your industry or community?")
    
    # Always ask about personality (never in resume)
    gaps.append("How would your friends or colleagues describe you in three words?")
    
    # Check for missing summary/objective
    if not basics.get("summary"):
        gaps.append("Can you give me a brief introduction about yourself and your professional journey?")
    
    # If they have work experience, ask about proudest achievement
    if work:
        gaps.append("Of all your professional experiences, what achievement are you most proud of and why?")
    
    # Check for interests/hobbies
    if not interests:
        gaps.append("What do you enjoy doing outside of work? Any hobbies or interests?")
    
    # Check for volunteer work
    if not volunteer:
        gaps.append("Have you been involved in any volunteer work or community activities?")
    
    # If they have projects, ask about motivation
    if projects:
        gaps.append("What motivated you to work on your personal projects?")
    
    # Ask about learning and growth
    gaps.append("What's something new you're learning or want to learn?")
    
    return gaps


def get_mime_type(filename: str) -> str:
    """Determine MIME type from filename."""
    lower_name = filename.lower()
    if lower_name.endswith('.pdf'):
        return 'application/pdf'
    elif lower_name.endswith('.docx'):
        return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    elif lower_name.endswith('.doc'):
        return 'application/msword'
    else:
        raise ValueError(f"Unsupported file type: {filename}. Please upload a PDF or Word document.")
