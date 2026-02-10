'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import ProgressIndicator from '@/components/questionnaire/progress-indicator';
import { getPhaseSteps } from '@/lib/questions';

interface ResumeData {
  basics?: {
    name?: string;
    email?: string;
    phone?: string;
    location?: { city?: string; region?: string; country?: string };
    summary?: string;
    profiles?: { network?: string; url?: string }[];
  };
  work?: {
    company?: string;
    position?: string;
    location?: string;
    startDate?: string;
    endDate?: string;
    summary?: string;
    highlights?: string[];
  }[];
  education?: {
    institution?: string;
    area?: string;
    studyType?: string;
    location?: string;
    startDate?: string;
    endDate?: string;
  }[];
  skills?: { category?: string; keywords?: string[] }[];
  languages?: { language?: string; fluency?: string }[];
  awards?: { title?: string; date?: string; awarder?: string; summary?: string }[];
}

interface ProfileAnalysis {
  profile_summary?: string;
  domain?: string;
  strengths?: { area: string; evidence: string[]; confidence: string }[];
  gaps?: { area: string; reason: string; priority: string }[];
  soft_skills_inference?: { skill: string; evidence: string; confidence: string }[];
  key_experiences?: string[];
}

export default function ProfilePreviewPage() {
  const [resume, setResume] = useState<ResumeData | null>(null);
  const [analysis, setAnalysis] = useState<ProfileAnalysis | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const resumeRaw = sessionStorage.getItem('resumeContext');
    const analysisRaw = sessionStorage.getItem('profileAnalysis');

    if (resumeRaw) {
      try { setResume(JSON.parse(resumeRaw)); } catch { /* ignore */ }
    }
    if (analysisRaw) {
      try { setAnalysis(JSON.parse(analysisRaw)); } catch { /* ignore */ }
    }
    setIsLoading(false);
  }, []);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40">
        <p className="text-gray-600">Loading your enhanced resume...</p>
      </div>
    );
  }

  if (!resume) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40">
        <div className="text-center space-y-4">
          <h1 className="text-2xl font-semibold text-gray-900">No resume data found</h1>
          <Link
            href="/profile/new"
            className="inline-block px-6 py-3 bg-msu-green text-white rounded-full hover:bg-msu-green-light transition-colors"
          >
            Start Over
          </Link>
        </div>
      </div>
    );
  }

  const basics = resume.basics || {};
  const locationStr = [basics.location?.city, basics.location?.region, basics.location?.country]
    .filter(Boolean)
    .join(', ');

  return (
    <div className="min-h-screen bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40">
      <div className="w-full pt-8 print:hidden">
        <ProgressIndicator currentStep={4} totalSteps={5} steps={getPhaseSteps()} />
      </div>

      <div className="max-w-3xl mx-auto px-4 py-8 print:py-4 print:px-0">
        <div className="bg-white rounded-2xl shadow-lg p-8 print:shadow-none print:rounded-none space-y-8">

          <header className="border-b border-gray-200 pb-6">
            <h1 className="text-3xl font-bold text-gray-900">{basics.name || 'Candidate'}</h1>
            {locationStr && <p className="text-gray-600 mt-1">{locationStr}</p>}
            <div className="flex flex-wrap gap-4 mt-3 text-sm text-gray-500">
              {basics.email && <span>{basics.email}</span>}
              {basics.phone && <span>{basics.phone}</span>}
              {basics.profiles?.map((p, i) => (
                <a key={i} href={p.url} target="_blank" rel="noopener noreferrer" className="text-msu-green hover:underline">
                  {p.network}
                </a>
              ))}
            </div>
          </header>

          {(analysis?.profile_summary || basics.summary) && (
            <section>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Summary</h2>
              <p className="text-gray-700 leading-relaxed">
                {analysis?.profile_summary || basics.summary}
              </p>
              {analysis?.domain && (
                <p className="mt-2 text-sm text-msu-green font-medium">Domain: {analysis.domain}</p>
              )}
            </section>
          )}

          {analysis?.strengths && analysis.strengths.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Key Strengths</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                {analysis.strengths.map((s, i) => (
                  <div key={i} className="p-3 bg-emerald-50/50 rounded-xl border border-emerald-100">
                    <p className="font-medium text-gray-800">{s.area}</p>
                    {s.evidence.length > 0 && (
                      <p className="text-sm text-gray-600 mt-1">{s.evidence[0]}</p>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {resume.work && resume.work.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Experience</h2>
              <div className="space-y-5">
                {resume.work.map((job, i) => (
                  <div key={i}>
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-semibold text-gray-900">{job.position}</p>
                        <p className="text-gray-600">{job.company}{job.location ? ` — ${job.location}` : ''}</p>
                      </div>
                      <p className="text-sm text-gray-500 flex-shrink-0 ml-4">
                        {job.startDate}{job.endDate ? ` – ${job.endDate}` : ' – Present'}
                      </p>
                    </div>
                    {job.summary && <p className="text-gray-700 mt-2 text-sm">{job.summary}</p>}
                    {job.highlights && job.highlights.length > 0 && (
                      <ul className="mt-2 space-y-1">
                        {job.highlights.map((h, j) => (
                          <li key={j} className="flex items-start gap-2 text-sm text-gray-700">
                            <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-msu-green flex-shrink-0" />
                            {h}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {resume.education && resume.education.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Education</h2>
              <div className="space-y-3">
                {resume.education.map((edu, i) => (
                  <div key={i} className="flex items-start justify-between">
                    <div>
                      <p className="font-semibold text-gray-900">
                        {edu.studyType}{edu.area ? ` in ${edu.area}` : ''}
                      </p>
                      <p className="text-gray-600">{edu.institution}{edu.location ? ` — ${edu.location}` : ''}</p>
                    </div>
                    <p className="text-sm text-gray-500 flex-shrink-0 ml-4">
                      {edu.startDate}{edu.endDate ? ` – ${edu.endDate}` : ''}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {resume.skills && resume.skills.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Skills</h2>
              <div className="space-y-2">
                {resume.skills.map((group, i) => (
                  <div key={i}>
                    {group.category && (
                      <span className="text-sm font-medium text-gray-600">{group.category}: </span>
                    )}
                    <span className="text-sm text-gray-700">{group.keywords?.join(', ')}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {analysis?.soft_skills_inference && analysis.soft_skills_inference.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Soft Skills</h2>
              <div className="flex flex-wrap gap-2">
                {analysis.soft_skills_inference.map((s, i) => (
                  <span key={i} className="px-3 py-1.5 bg-gray-100 rounded-full text-sm text-gray-700 border border-gray-200">
                    {s.skill}
                  </span>
                ))}
              </div>
            </section>
          )}

          {analysis?.gaps && analysis.gaps.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Areas to Strengthen</h2>
              <div className="space-y-2">
                {analysis.gaps.map((g, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm">
                    <span className="mt-1 w-2 h-2 rounded-full bg-amber-400 flex-shrink-0" />
                    <div>
                      <span className="font-medium text-gray-800">{g.area}</span>
                      <span className="text-gray-500"> — {g.reason}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {resume.languages && resume.languages.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Languages</h2>
              <div className="flex flex-wrap gap-3">
                {resume.languages.map((l, i) => (
                  <span key={i} className="text-sm text-gray-700">
                    {l.language}{l.fluency ? ` (${l.fluency})` : ''}
                  </span>
                ))}
              </div>
            </section>
          )}

          {resume.awards && resume.awards.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Awards</h2>
              <div className="space-y-2">
                {resume.awards.map((a, i) => (
                  <div key={i}>
                    <span className="font-medium text-gray-800">{a.title}</span>
                    {a.awarder && <span className="text-gray-500"> — {a.awarder}</span>}
                    {a.date && <span className="text-sm text-gray-400 ml-2">{a.date}</span>}
                  </div>
                ))}
              </div>
            </section>
          )}

        </div>

        <div className="flex justify-center gap-4 mt-8 print:hidden">
          <button
            onClick={() => window.print()}
            className="px-6 py-3 bg-white text-gray-700 rounded-full shadow-lg hover:shadow-xl transition-all border border-gray-200 font-medium"
          >
            Export PDF
          </button>
          <Link
            href="/profile/new"
            className="px-6 py-3 bg-msu-green text-white rounded-full shadow-lg hover:shadow-xl hover:bg-msu-green-light transition-all font-medium"
          >
            Create New Profile
          </Link>
        </div>
      </div>
    </div>
  );
}
