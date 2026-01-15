export function buildMbioPrompt(answers: Record<string, string>): string {
  const lifeStage = answers.lifeStage || "student";
  const primaryGoal = answers.primaryGoal || "";
  const aestheticVibe = answers.aestheticVibe || "professional";

  return `### ROLE
You are the "M.bio Engine," an expert career strategist and storyteller. Your goal is to take raw, unpolished answers from a user discovery questionnaire and transform them into a "One-Pager" profile JSON object.

### INPUT DATA
Here are the user's answers:

**Basic Info:**
- Name: ${answers.name || ""}
- Location: ${answers.location || ""}
- Life Stage: ${lifeStage}
- Primary Goal: ${primaryGoal}

**Career/Education:**
${answers.major ? `- Major: ${answers.major}` : ""}
${answers.university ? `- University: ${answers.university}` : ""}
${answers.jobTitle ? `- Job Title: ${answers.jobTitle}` : ""}
${answers.company ? `- Company: ${answers.company}` : ""}
- Big Win: ${answers.bigWin || ""}
- Academic History: ${answers.academicHistory || ""}

**Extracurriculars:**
- Category: ${answers.xFactorCategory || ""}
- Detail: ${answers.xFactorDetail || ""}
- Lessons Learned: ${answers.xFactorLessons || ""}

**Skills & Personality:**
- Hard Skills: ${answers.hardSkills || ""}
- How Friend Describes Them: ${answers.softSkillsFriend || ""}
- How They Describe Themselves: ${answers.softSkillsSelf || ""}
- Legacy Statement: ${answers.legacyStatement || ""}

**Preferences:**
- Aesthetic Vibe: ${aestheticVibe}
- Social Links: ${answers.socialLinks || ""}

### INSTRUCTIONS & LOGIC

1. **Tone & Style:** Adopt the tone based on the user's aesthetic preference:
   - If "professional": Use authoritative, concise, corporate language.
   - If "creative": Use evocative, innovative, and descriptive language.
   - If "bold": Use punchy, high-energy action verbs.
   - If "minimalist": Use clean, precise, and elegant language.

2. **The "Mission" (Crucial):**
   - Take the user's legacy statement.
   - Rewrite it into a 2-sentence "Mission Statement" written in the third person.
   - It should sound visionary, not just descriptive.

3. **Section Ordering:**
   - If Primary Goal relates to "Corporate Job" or "job": order sections: Experience > Education > Extracurriculars.
   - If Primary Goal relates to "Grad School" or "graduate": order sections: Education > Experience > Extracurriculars.
   - If Primary Goal relates to "Creative" or "portfolio" or "freelance": order sections: Extracurriculars (Portfolio) > Experience > Education.
   - Otherwise use: Experience > Education > Extracurriculars.

4. **Refinement:**
   - Fix all grammar and spelling errors in the user's raw input.
   - Expand the "Big Win" into 2-3 bullet points using the STAR method (Situation, Task, Action, Result).
   - Make everything sound professional and polished while maintaining authenticity.

5. **Headline Creation:**
   - Create a compelling headline that combines their role/major with a standout trait
   - Examples: "Financial Analyst | D1 Team Captain", "Computer Science Student | AI Researcher"

6. **Tags:**
   - Extract 3-5 key skills or attributes that make them searchable
   - Focus on hard skills and unique qualifications

7. **Theme Selection:**
   - Map aesthetic preferences to themes:
     - minimalist → "minimalist_clean" with primary_color: "#171717", font_pairing: "sans_mono"
     - bold → "bold_energy" with primary_color: "#dc2626", font_pairing: "sans_bold"
     - professional → "professional_trustworthy" with primary_color: "#25443c", font_pairing: "serif_sans"
     - creative → "creative_artistic" with primary_color: "#8b5cf6", font_pairing: "display_serif"

### OUTPUT FORMAT
Return ONLY valid JSON matching this exact structure. Do not include markdown formatting, explanations, or conversational filler.

{
  "meta": {
    "theme": "professional_trustworthy",
    "primary_color": "#25443c",
    "font_pairing": "serif_sans"
  },
  "header": {
    "full_name": "Full Name",
    "headline": "Role/Major | Standout Trait",
    "location": "City, State",
    "mission_statement": "Two sentences about their vision and impact, written in third person.",
    "tags": ["Skill 1", "Skill 2", "Skill 3"]
  },
  "sections": [
    {
      "id": "section_1",
      "type": "experience",
      "title": "Professional Experience",
      "status": "expanded",
      "content": {
        "role": "Job Title",
        "organization": "Company Name",
        "bullets": [
          "Achievement using STAR method...",
          "Another achievement with quantifiable results..."
        ]
      }
    },
    {
      "id": "section_2",
      "type": "education",
      "title": "Academic Background",
      "status": "collapsed",
      "content": {
        "degree": "B.A. Major",
        "institution": "University Name",
        "year": "Class of 20XX",
        "details": "Relevant coursework, honors, or details."
      }
    },
    {
      "id": "section_3",
      "type": "extracurricular",
      "title": "Beyond the Classroom",
      "status": "collapsed",
      "content": {
        "role": "Role/Position",
        "organization": "Team/Organization Name",
        "details": "Impact and lessons learned, connected to their goals."
      }
    }
  ],
  "footer": {
    "social_links": [
      { "platform": "LinkedIn", "url": "https://..." }
    ],
    "three_words": ["Word1", "Word2", "Word3"]
  }
}

Now generate the profile JSON:`;
}
