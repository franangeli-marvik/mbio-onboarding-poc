export interface ProfileMeta {
  theme: 'minimalist' | 'bold' | 'professional' | 'creative';
  primary_color: string;
  font_pairing: string;
}

export interface ProfileHeader {
  full_name: string;
  headline: string;
  location: string;
  mission_statement: string;
  tags: string[];
}

export interface ProfileSection {
  id: string;
  type: 'experience' | 'education' | 'extracurricular';
  title: string;
  status: 'expanded' | 'collapsed';
  content: {
    role?: string;
    organization?: string;
    bullets?: string[];
    degree?: string;
    institution?: string;
    year?: string;
    details?: string;
  };
}

export interface ProfileFooter {
  social_links: {
    platform: string;
    url: string;
  }[];
  three_words: string[];
}

export interface GeneratedProfile {
  meta: ProfileMeta;
  header: ProfileHeader;
  sections: ProfileSection[];
  footer: ProfileFooter;
}
