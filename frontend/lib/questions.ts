export type QuestionType = "text" | "textarea" | "select" | "multiselect";

export interface Question {
  id: string;
  phase: "foundation" | "pillars" | "polish";
  phaseLabel: string;
  question: string;
  subtext?: string;
  type: QuestionType;
  options?: { value: string; label: string }[];
  conditional?: {
    dependsOn: string;
    values: string[];
  };
  placeholder?: string;
}

export const questions: Question[] = [
  // PHASE 1: FOUNDATION
  {
    id: "name",
    phase: "foundation",
    phaseLabel: "BASICS",
    question: "What's your full name?",
    subtext: "Let's start with the basics.",
    type: "text",
    placeholder: "e.g., Marcus Washington",
  },
  {
    id: "location",
    phase: "foundation",
    phaseLabel: "BASICS",
    question: "Where are you located?",
    subtext: "City and state are perfect.",
    type: "text",
    placeholder: "e.g., Chicago, IL",
  },
  {
    id: "lifeStage",
    phase: "foundation",
    phaseLabel: "BASICS",
    question: "Which best describes your current stage?",
    subtext: "This helps us tailor your profile.",
    type: "select",
    options: [
      { value: "student", label: "Student" },
      { value: "recent_grad", label: "Recent Grad (0-5 years exp)" },
      { value: "professional", label: "Experienced Professional" },
      { value: "creator", label: "Creator / Freelancer / Artist" },
    ],
  },
  {
    id: "primaryGoal",
    phase: "foundation",
    phaseLabel: "BASICS",
    question: "What's your primary goal right now?",
    subtext: "In your own words - what are you working toward?",
    type: "textarea",
    placeholder:
      "e.g., Landing a corporate job in finance, Getting into grad school, Building my freelance portfolio...",
  },

  // PHASE 2: PILLARS
  {
    id: "major",
    phase: "pillars",
    phaseLabel: "SCHOOL",
    question: "What's your major or degree?",
    subtext: "Tell us what you're studying.",
    type: "text",
    placeholder: "e.g., Economics, Computer Science, Business Administration",
    conditional: {
      dependsOn: "lifeStage",
      values: ["student"],
    },
  },
  {
    id: "university",
    phase: "pillars",
    phaseLabel: "SCHOOL",
    question: "Which university do you attend?",
    type: "text",
    placeholder: "e.g., Michigan State University",
    conditional: {
      dependsOn: "lifeStage",
      values: ["student"],
    },
  },
  {
    id: "jobTitle",
    phase: "pillars",
    phaseLabel: "SCHOOL",
    question: "What's your current or most recent job title?",
    type: "text",
    placeholder: "e.g., Summer Analyst, Marketing Intern",
    conditional: {
      dependsOn: "lifeStage",
      values: ["recent_grad", "professional"],
    },
  },
  {
    id: "company",
    phase: "pillars",
    phaseLabel: "SCHOOL",
    question: "Which company or organization?",
    type: "text",
    placeholder: "e.g., Goldman Sachs, Google, Local Startup",
    conditional: {
      dependsOn: "lifeStage",
      values: ["recent_grad", "professional"],
    },
  },
  {
    id: "bigWin",
    phase: "pillars",
    phaseLabel: "SCHOOL",
    question: "Tell us about your biggest accomplishment.",
    subtext:
      "Don't worry about perfect grammar - just tell us what happened and what you're proud of.",
    type: "textarea",
    placeholder:
      "e.g., Led a team of 5 to launch a new product feature that increased user engagement by 40%...",
  },
  {
    id: "academicHistory",
    phase: "pillars",
    phaseLabel: "SCHOOL",
    question: "Any academic awards, honors, or relevant coursework?",
    subtext:
      "Dean's List, scholarships, key projects - anything that stands out.",
    type: "textarea",
    placeholder:
      "e.g., Dean's List Fall 2024, Presidential Scholarship, Advanced Financial Modeling course...",
  },
  {
    id: "xFactorCategory",
    phase: "pillars",
    phaseLabel: "LIFE",
    question: "Outside work and school, how do you spend your time?",
    subtext: "Select your main area of interest.",
    type: "select",
    options: [
      { value: "sports", label: "Organized Sports" },
      { value: "volunteering", label: "Volunteering" },
      { value: "creative", label: "Creative Arts" },
      { value: "tech", label: "Tech Side-Projects" },
      { value: "travel", label: "Travel/Culture" },
      { value: "other", label: "Other" },
    ],
  },
  {
    id: "xFactorDetail",
    phase: "pillars",
    phaseLabel: "LIFE",
    question: "Tell us about a specific achievement or role in that area.",
    subtext: "What did you accomplish? What role did you play?",
    type: "textarea",
    placeholder:
      "e.g., Team Captain of D1 Football, won Rose Bowl Championship...",
  },
  {
    id: "xFactorLessons",
    phase: "pillars",
    phaseLabel: "LIFE",
    question: "What valuable lessons did you learn?",
    subtext: "How do these experiences connect to your goals?",
    type: "textarea",
    placeholder:
      "e.g., Being team captain taught me the importance of open communication and how to motivate a diverse group...",
  },

  // PHASE 3: POLISH
  {
    id: "hardSkills",
    phase: "polish",
    phaseLabel: "SKILLS",
    question: "What are your top 5 tools or technical skills?",
    subtext: "The software, languages, or technical abilities you use most.",
    type: "textarea",
    placeholder: "e.g., Python, Excel, Financial Modeling, JIRA, Figma",
  },
  {
    id: "softSkillsFriend",
    phase: "polish",
    phaseLabel: "SKILLS",
    question: "How would your best friend describe you in three words?",
    subtext: "Think about what they'd say about your personality.",
    type: "text",
    placeholder: "e.g., Relentless, Empathetic, Analytical",
  },
  {
    id: "softSkillsSelf",
    phase: "polish",
    phaseLabel: "SKILLS",
    question: "How would you describe yourself in three words?",
    type: "text",
    placeholder: "e.g., Creative, Disciplined, Curious",
  },
  {
    id: "legacyStatement",
    phase: "polish",
    phaseLabel: "IMPACT",
    question: "What impact do you want to make?",
    subtext:
      "Think big - how do you want to change your industry, community, or the world?",
    type: "textarea",
    placeholder:
      "e.g., I want to help athletes build generational wealth and stop the cycle of financial instability...",
  },
  // {
  //   id: 'aestheticVibe',
  //   phase: 'polish',
  //   phaseLabel: 'IMPACT',
  //   question: "Which aesthetic feels most you?",
  //   subtext: "This will determine your profile's visual style.",
  //   type: 'select',
  //   options: [
  //     { value: 'minimalist', label: 'Minimalist & Clean' },
  //     { value: 'bold', label: 'Bold & High Energy' },
  //     { value: 'professional', label: 'Professional & Trustworthy' },
  //     { value: 'creative', label: 'Creative & Artistic' }
  //   ]
  // },
  {
    id: "socialLinks",
    phase: "polish",
    phaseLabel: "IMPACT",
    question: "Where else can people find you?",
    subtext:
      "LinkedIn, GitHub, portfolio site, Instagram - paste any relevant URLs.",
    type: "textarea",
    placeholder: "e.g., linkedin.com/in/yourname, github.com/username",
  },
];

export function getVisibleQuestions(
  allQuestions: Question[],
  answers: Record<string, string>
): Question[] {
  return allQuestions.filter((q) => {
    if (!q.conditional) return true;

    const dependencyValue = answers[q.conditional.dependsOn];
    return q.conditional.values.includes(dependencyValue);
  });
}

export function getPhaseSteps(): string[] {
  return ["BASICS", "SCHOOL", "LIFE", "SKILLS", "IMPACT"];
}
