'use client';

import { GeneratedProfile } from '@/lib/types';
import { useState, useRef } from 'react';

interface ProfileCardProps {
  profile: GeneratedProfile;
}

export default function ProfileCard({ profile }: ProfileCardProps) {
  // Start with all sections expanded
  const [expandedSections, setExpandedSections] = useState<Set<string>>(() => {
    const allSections = new Set(profile.sections.map(s => s.id));
    return allSections;
  });

  const [profileImage, setProfileImage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImageClick = () => {
    fileInputRef.current?.click();
  };

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const imageUrl = URL.createObjectURL(file);
      setProfileImage(imageUrl);
    }
  };

  const toggleSection = (id: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // Map section type to hashtag label
  const getSectionLabel = (type: string, title: string) => {
    const labels: Record<string, string> = {
      experience: '#experience',
      education: '#education',
      extracurricular: '#beyond',
    };
    return labels[type] || `#${title.toLowerCase().replace(/\s+/g, '')}`;
  };

  return (
    <div className="min-h-screen bg-gray-100 py-8 px-4 print:bg-white print:py-0 print:px-0">
      <div className="max-w-6xl mx-auto">
        <div className="bg-white rounded-2xl shadow-lg overflow-hidden print:shadow-none print:rounded-none">
          <div className="flex flex-col lg:flex-row">
            {/* Hidden file input for photo upload */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleImageChange}
              accept="image/*"
              className="hidden"
            />

            {/* Left Column - hidden on mobile and print */}
            <div className="hidden lg:block lg:w-[400px] p-6 lg:border-r border-gray-100 print:hidden">
              {/* Large Profile Photo Placeholder */}
              <div
                onClick={handleImageClick}
                className="max-h-[300px] lg:max-h-none aspect-[4/5] bg-gradient-to-br from-gray-200 to-gray-300 rounded-xl flex items-center justify-center cursor-pointer hover:from-gray-300 hover:to-gray-400 transition-colors group overflow-hidden"
              >
                {profileImage ? (
                  <img
                    src={profileImage}
                    alt="Profile"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="text-center text-gray-500 group-hover:text-gray-600">
                    <svg className="w-16 h-16 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                    <p className="text-sm font-medium">Click to add photo</p>
                  </div>
                )}
              </div>

              {/* Skills/Tags Section */}
              <div className="mt-6 space-y-4">
                <div className="flex flex-wrap gap-2">
                  {profile.header.tags.map((tag, index) => (
                    <span
                      key={index}
                      className="px-3 py-1.5 bg-gray-100 rounded-full text-sm text-gray-700 border border-gray-200"
                    >
                      {tag}
                    </span>
                  ))}
                </div>

                {/* Three Words */}
                <div className="pt-4 border-t border-gray-100">
                  <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Described as</p>
                  <div className="flex flex-wrap gap-2">
                    {profile.footer.three_words.map((word, index) => (
                      <span
                        key={index}
                        className="px-3 py-1.5 bg-gray-100 rounded-full text-sm font-medium text-gray-700 border border-gray-200"
                      >
                        {word}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Social Links - hidden in print */}
                {profile.footer.social_links.length > 0 && (
                  <div className="pt-4 border-t border-gray-100 print:hidden">
                    <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Connect</p>
                    <div className="flex flex-wrap gap-2">
                      {profile.footer.social_links.map((link, index) => (
                        <a
                          key={index}
                          href={link.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-full text-sm text-gray-700 transition-colors"
                        >
                          {link.platform}
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Right Column */}
            <div className="flex-1 p-6 lg:p-8">
              {/* Header */}
              <div className="mb-8 pb-6 border-b border-gray-200">
                {/* Small circle photo - mobile only */}
                <div
                  onClick={handleImageClick}
                  className="w-16 h-16 mb-4 lg:hidden print:hidden cursor-pointer"
                >
                  <div className="w-full h-full bg-gradient-to-br from-gray-200 to-gray-300 rounded-full flex items-center justify-center border-2 border-dashed border-gray-300 overflow-hidden hover:from-gray-300 hover:to-gray-400 transition-colors">
                    {profileImage ? (
                      <img
                        src={profileImage}
                        alt="Profile"
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                      </svg>
                    )}
                  </div>
                </div>
                <h1 className="text-3xl lg:text-4xl font-bold text-gray-900 mb-1">
                  {profile.header.full_name}
                </h1>
                <p className="text-lg text-gray-600">
                  {profile.header.headline}
                </p>
                <p className="text-sm text-gray-500 mt-2">
                  {profile.header.location}
                </p>
              </div>

              {/* Introduction Section - always visible */}
              <div className="mb-6 pb-6 border-b border-gray-100">
                <p className="text-gray-400 text-sm font-medium mb-3">#introduction</p>
                <p className="text-gray-700 leading-relaxed">
                  {profile.header.mission_statement}
                </p>
              </div>

              {/* Dynamic Sections */}
              {profile.sections.map((section) => (
                <div key={section.id} className="mb-6 pb-6 border-b border-gray-100 last:border-0">
                  <button
                    onClick={() => toggleSection(section.id)}
                    className="flex items-center justify-between w-full text-left group"
                  >
                    <span className="text-gray-400 text-sm font-medium">
                      {getSectionLabel(section.type, section.title)}
                    </span>
                    <svg
                      className={`w-5 h-5 text-gray-400 transition-transform print:hidden ${
                        expandedSections.has(section.id) ? 'rotate-180' : ''
                      }`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>

                  <div className={`mt-4 ${expandedSections.has(section.id) ? 'block' : 'hidden'} print:!block`}>
                    {section.type === 'experience' && section.content.role && (
                      <div className="space-y-3">
                        <div>
                          <p className="text-lg font-semibold text-gray-900">{section.content.role}</p>
                          <p className="text-gray-600">{section.content.organization}</p>
                        </div>
                        {section.content.bullets && section.content.bullets.length > 0 && (
                          <ul className="space-y-2 text-gray-700">
                            {section.content.bullets.map((bullet, i) => (
                              <li key={i} className="flex items-start gap-2">
                                <span
                                  className="mt-2 w-1.5 h-1.5 rounded-full flex-shrink-0"
                                  style={{ backgroundColor: profile.meta.primary_color }}
                                />
                                <span className="leading-relaxed">{bullet}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}

                    {section.type === 'education' && section.content.degree && (
                      <div className="space-y-1">
                        <p className="text-lg font-semibold text-gray-900">{section.content.degree}</p>
                        <p className="text-gray-600">{section.content.institution}</p>
                        {section.content.year && (
                          <p className="text-sm text-gray-500">{section.content.year}</p>
                        )}
                        {section.content.details && (
                          <p className="text-gray-700 mt-3 leading-relaxed">{section.content.details}</p>
                        )}
                      </div>
                    )}

                    {section.type === 'extracurricular' && (
                      <div className="space-y-1">
                        {section.content.role && (
                          <p className="text-lg font-semibold text-gray-900">{section.content.role}</p>
                        )}
                        {section.content.organization && (
                          <p className="text-gray-600">{section.content.organization}</p>
                        )}
                        {section.content.details && (
                          <p className="text-gray-700 mt-3 leading-relaxed">{section.content.details}</p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {/* Mobile-only: Tags, Described As, Connect - hidden on desktop */}
              <div className="lg:hidden mt-6 space-y-6">
                {/* Tags */}
                <div className="flex flex-wrap gap-2">
                  {profile.header.tags.map((tag, index) => (
                    <span
                      key={index}
                      className="px-3 py-1.5 bg-gray-100 rounded-full text-sm text-gray-700 border border-gray-200"
                    >
                      {tag}
                    </span>
                  ))}
                </div>

                {/* Three Words */}
                <div className="pt-4 border-t border-gray-100">
                  <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Described as</p>
                  <div className="flex flex-wrap gap-2">
                    {profile.footer.three_words.map((word, index) => (
                      <span
                        key={index}
                        className="px-3 py-1.5 bg-gray-100 rounded-full text-sm font-medium text-gray-700 border border-gray-200"
                      >
                        {word}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Social Links - hidden in print */}
                {profile.footer.social_links.length > 0 && (
                  <div className="pt-4 border-t border-gray-100 print:hidden">
                    <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Connect</p>
                    <div className="flex flex-wrap gap-2">
                      {profile.footer.social_links.map((link, index) => (
                        <a
                          key={index}
                          href={link.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-full text-sm text-gray-700 transition-colors"
                        >
                          {link.platform}
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
