import { GeneratedProfile } from './types';

export const demoProfile: GeneratedProfile = {
  meta: {
    theme: 'professional',
    primary_color: '#25443c',
    font_pairing: 'serif_sans'
  },
  header: {
    full_name: 'Marcus Washington',
    headline: 'Finance Student | D1 Football Captain',
    location: 'East Lansing, MI',
    mission_statement: 'Driven to break the cycle of financial instability in athletics. Marcus builds robust financial structures that transform short-term success into multi-generational wealth for underserved families.',
    tags: ['Financial Modeling', 'Leadership', 'Portfolio Analysis', 'Excel', 'Risk Management']
  },
  sections: [
    {
      id: 'section_1',
      type: 'experience',
      title: 'Professional Experience',
      status: 'expanded',
      content: {
        role: 'Summer Analyst',
        organization: 'Goldman Sachs (Private Wealth Management)',
        bullets: [
          'Analyzed high-net-worth portfolios for professional athlete clients, identifying market inefficiencies that increased projected annual yield by 4% across $15M in managed assets',
          'Developed automated Excel macros utilizing VBA to streamline weekly portfolio reporting, reducing manual data entry time by 30% and eliminating reconciliation errors',
          'Conducted comprehensive risk assessments and stress tests to align investment strategies with long-term wealth preservation goals for clients transitioning from active careers'
        ]
      }
    },
    {
      id: 'section_2',
      type: 'education',
      title: 'Academic Background',
      status: 'collapsed',
      content: {
        degree: 'B.A. Economics',
        institution: 'Michigan State University',
        year: 'Class of 2025',
        details: 'Dean\'s List (Fall 2023, Spring 2024). Presidential Scholarship recipient. Coursework focus: Advanced Financial Modeling, Macroeconomic Theory, Portfolio Management, and Behavioral Economics.'
      }
    },
    {
      id: 'section_3',
      type: 'extracurricular',
      title: 'Beyond the Classroom',
      status: 'collapsed',
      content: {
        role: 'Team Captain',
        organization: 'MSU Spartans Football',
        details: 'Led roster of 100+ athletes while maintaining academic excellence and managing 40+ hour weekly commitment. Developed leadership philosophy centered on open communication and individual accountability. Rose Bowl participant (2024).'
      }
    }
  ],
  footer: {
    social_links: [
      { platform: 'LinkedIn', url: 'https://linkedin.com/in/marcus-washington' },
      { platform: 'GitHub', url: 'https://github.com/mwashington' }
    ],
    three_words: ['Disciplined', 'Analytical', 'Visionary']
  }
};
