"""
Feature Extraction Module for MBIO Profile Creation
Extracts structured profile data from interview transcripts based on fields.csv schema.
"""

import json
import os
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

openai_client = OpenAI()

# Profile fields based on fields.csv structure
PROFILE_FIELDS = {
    "basics": {
        "first_name": "User's first name",
        "last_name": "User's last name",
        "location": {
            "city": "City name",
            "state": "State/Province",
            "country": "Country"
        },
        "headline": "Professional headline (e.g., 'Finance Student | D1 Football Captain')",
        "mission_statement": "Personal mission or introduction statement"
    },
    "experience": [
        {
            "type": "Type of experience (internship, full-time, part-time, freelance, volunteer)",
            "title": "Job title/role",
            "organization": {
                "name": "Company/organization name",
                "industry": "Industry sector"
            },
            "start_date": "Start date (month/year)",
            "end_date": "End date or 'Present'",
            "description": "Role description and achievements",
            "bullets": ["Achievement 1", "Achievement 2", "Achievement 3"]
        }
    ],
    "education": [
        {
            "level": "Education level (high school, bachelor, master, phd)",
            "degree": "Degree name (e.g., B.A. Economics)",
            "institution": "University/school name",
            "year": "Graduation year or expected year",
            "details": "Additional details (honors, coursework, GPA)"
        }
    ],
    "skills": {
        "hard_skills": ["Technical skill 1", "Technical skill 2"],
        "soft_skills": ["Soft skill 1", "Soft skill 2"],
        "tools": ["Tool/software 1", "Tool/software 2"]
    },
    "extracurricular": [
        {
            "type": "Type (sports, clubs, volunteering, music_art)",
            "title": "Role or position",
            "organization": "Organization/team name",
            "description": "Description of involvement and achievements"
        }
    ],
    "honors_awards": [
        {
            "title": "Award name",
            "issuer": "Issuing organization",
            "date": "Date received",
            "description": "Brief description"
        }
    ],
    "personality": {
        "three_words_friend": ["Word 1", "Word 2", "Word 3"],
        "three_words_self": ["Word 1", "Word 2", "Word 3"]
    },
    "goals": {
        "primary_goal": "Main career/life goal",
        "impact_statement": "What impact they want to make"
    },
    "social_links": [
        {
            "platform": "Platform name (LinkedIn, GitHub, etc.)",
            "url": "Full URL"
        }
    ]
}

EXTRACTION_PROMPT = """
You are a profile data extractor. Analyze the interview transcript and extract structured profile information.

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
            "bullets": ["achievement 1", "achievement 2", ...]
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
        "hard_skills": ["skill1", "skill2", ...],
        "soft_skills": ["skill1", "skill2", ...],
        "tools": ["tool1", "tool2", ...]
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

Return ONLY valid JSON, no additional text.
"""


def extract_profile_features(
    transcript: list[dict],
    basics_answers: dict,
    model: str = "gpt-4o"
) -> dict:
    """
    Extract structured profile features from an interview transcript.
    
    Args:
        transcript: List of {"role": "user"|"agent", "text": "...", "timestamp": ...}
        basics_answers: Dict with name, location, lifeStage from the form
        model: OpenAI model to use for extraction
    
    Returns:
        Dictionary with extracted profile data
    """
    if not transcript:
        return create_empty_profile(basics_answers)
    
    # Format transcript
    transcript_text = "\n".join([
        f"{'USER' if item['role'] == 'user' else 'INTERVIEWER'}: {item['text']}" 
        for item in transcript
        if item.get('text')
    ])
    
    # Format basics
    basics_text = json.dumps(basics_answers, indent=2)
    
    prompt = EXTRACTION_PROMPT.format(
        transcript=transcript_text,
        basics=basics_text
    )
    
    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a professional profile data extractor. Extract structured data from interview transcripts."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        extracted = json.loads(response.choices[0].message.content)
        
        # Merge with basics answers
        if basics_answers.get('name'):
            names = basics_answers['name'].split()
            extracted.setdefault('basics', {})
            extracted['basics']['first_name'] = names[0]
            if len(names) > 1:
                extracted['basics']['last_name'] = ' '.join(names[1:])
        
        if basics_answers.get('location'):
            extracted.setdefault('basics', {})
            extracted['basics'].setdefault('location', {})
            # Try to parse location
            loc_parts = basics_answers['location'].split(',')
            if len(loc_parts) >= 2:
                extracted['basics']['location']['city'] = loc_parts[0].strip()
                extracted['basics']['location']['state'] = loc_parts[-1].strip()
        
        return extracted
        
    except Exception as e:
        print(f"[ERROR] Feature extraction failed: {e}")
        return create_empty_profile(basics_answers)


def create_empty_profile(basics_answers: dict) -> dict:
    """Create an empty profile structure with basics filled in."""
    profile = {
        "basics": {
            "first_name": "",
            "last_name": "",
            "location": {"city": "", "state": "", "country": ""},
            "headline": "",
            "mission_statement": ""
        },
        "experience": [],
        "education": [],
        "skills": {"hard_skills": [], "soft_skills": [], "tools": []},
        "extracurricular": [],
        "honors_awards": [],
        "personality": {"three_words_friend": [], "three_words_self": []},
        "goals": {"primary_goal": "", "impact_statement": ""},
        "social_links": []
    }
    
    if basics_answers.get('name'):
        names = basics_answers['name'].split()
        profile['basics']['first_name'] = names[0]
        if len(names) > 1:
            profile['basics']['last_name'] = ' '.join(names[1:])
    
    if basics_answers.get('location'):
        profile['basics']['location']['city'] = basics_answers['location']
    
    return profile


def convert_to_profile_format(extracted: dict) -> dict:
    """
    Convert extracted features to the GeneratedProfile format expected by the frontend.
    
    Returns a profile matching the TypeScript GeneratedProfile interface.
    """
    basics = extracted.get('basics', {})
    skills = extracted.get('skills', {})
    personality = extracted.get('personality', {})
    goals = extracted.get('goals', {})
    
    # Build full name
    full_name = basics.get('first_name', '')
    if basics.get('last_name'):
        full_name += ' ' + basics['last_name']
    
    # Build location string
    location_parts = []
    loc = basics.get('location', {})
    if loc.get('city'):
        location_parts.append(loc['city'])
    if loc.get('state'):
        location_parts.append(loc['state'])
    location_str = ', '.join(location_parts) if location_parts else ''
    
    # Build tags from skills
    all_skills = (
        skills.get('hard_skills', [])[:3] + 
        skills.get('tools', [])[:2]
    )
    
    # Build sections
    sections = []
    
    # Experience sections
    for exp in extracted.get('experience', []):
        sections.append({
            "id": f"exp-{len(sections)}",
            "type": "experience",
            "title": exp.get('title', 'Experience'),
            "status": "expanded",
            "content": {
                "role": exp.get('title', ''),
                "organization": exp.get('organization', {}).get('name', ''),
                "bullets": exp.get('bullets', [])
            }
        })
    
    # Education sections
    for edu in extracted.get('education', []):
        sections.append({
            "id": f"edu-{len(sections)}",
            "type": "education",
            "title": edu.get('degree', 'Education'),
            "status": "expanded",
            "content": {
                "degree": edu.get('degree', ''),
                "institution": edu.get('institution', ''),
                "year": edu.get('year', ''),
                "details": edu.get('details', '')
            }
        })
    
    # Extracurricular sections
    for extra in extracted.get('extracurricular', []):
        sections.append({
            "id": f"extra-{len(sections)}",
            "type": "extracurricular",
            "title": extra.get('title', 'Activity'),
            "status": "expanded",
            "content": {
                "role": extra.get('title', ''),
                "organization": extra.get('organization', ''),
                "details": extra.get('description', '')
            }
        })
    
    # Build social links
    social_links = []
    for link in extracted.get('social_links', []):
        social_links.append({
            "platform": link.get('platform', 'Link'),
            "url": link.get('url', '')
        })
    
    # Combine personality words
    three_words = (
        personality.get('three_words_friend', [])[:2] +
        personality.get('three_words_self', [])[:1]
    )
    
    return {
        "meta": {
            "theme": "professional",
            "primary_color": "#25443c",
            "font_pairing": "serif"
        },
        "header": {
            "full_name": full_name,
            "headline": basics.get('headline', ''),
            "location": location_str,
            "mission_statement": basics.get('mission_statement', goals.get('impact_statement', '')),
            "tags": all_skills[:5]
        },
        "sections": sections,
        "footer": {
            "social_links": social_links,
            "three_words": three_words[:3]
        }
    }
