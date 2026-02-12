'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import ProgressIndicator from '@/components/questionnaire/progress-indicator';
import ProfileCard from '@/components/profile/profile-card';
import { getPhaseSteps } from '@/lib/questions';
import { GeneratedProfile } from '@/lib/types';

type TabId = 'original' | 'enhanced' | 'edited';

export default function ProfilePreviewPage() {
  const [originalProfile, setOriginalProfile] = useState<GeneratedProfile | null>(null);
  const [enhancedProfile, setEnhancedProfile] = useState<GeneratedProfile | null>(null);
  const [editedProfile, setEditedProfile] = useState<GeneratedProfile | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>('enhanced');
  const [isLoading, setIsLoading] = useState(true);
  const [editSaved, setEditSaved] = useState(false);

  useEffect(() => {
    const originalRaw = sessionStorage.getItem('originalProfile');
    const enhancedRaw = sessionStorage.getItem('enhancedProfile');
    const editedRaw = sessionStorage.getItem('editedProfile');

    if (originalRaw) {
      try { setOriginalProfile(JSON.parse(originalRaw)); } catch { /* ignore */ }
    }
    if (enhancedRaw) {
      try {
        const parsed = JSON.parse(enhancedRaw);
        setEnhancedProfile(parsed);
        if (!editedRaw) {
          setEditedProfile(JSON.parse(JSON.stringify(parsed)));
        }
      } catch { /* ignore */ }
    }
    if (editedRaw) {
      try { setEditedProfile(JSON.parse(editedRaw)); } catch { /* ignore */ }
    }

    setIsLoading(false);
  }, []);

  const handleSaveEdited = () => {
    if (editedProfile) {
      sessionStorage.setItem('editedProfile', JSON.stringify(editedProfile));
      setEditSaved(true);
      setTimeout(() => setEditSaved(false), 2000);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40">
        <p className="text-gray-600">Loading your enhanced resume...</p>
      </div>
    );
  }

  if (!enhancedProfile && !originalProfile) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40">
        <div className="text-center space-y-4">
          <h1 className="text-2xl font-semibold text-gray-900">No profile data found</h1>
          <p className="text-gray-500">Complete the interview process to generate your enhanced resume.</p>
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

  const tabs: { id: TabId; label: string; available: boolean }[] = [
    { id: 'original', label: 'Original', available: !!originalProfile },
    { id: 'enhanced', label: 'Enhanced', available: !!enhancedProfile },
    { id: 'edited', label: 'Edited', available: !!editedProfile },
  ];

  const currentProfile = activeTab === 'original'
    ? originalProfile
    : activeTab === 'enhanced'
    ? enhancedProfile
    : editedProfile;

  return (
    <div className="min-h-screen bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40">
      <div className="w-full pt-8 print:hidden">
        <ProgressIndicator currentStep={4} totalSteps={5} steps={getPhaseSteps()} />
      </div>

      <div className="max-w-6xl mx-auto px-4 py-6 print:py-0 print:px-0">
        <div className="flex items-center justify-between mb-6 print:hidden">
          <div className="flex items-center gap-1 p-1 bg-white rounded-xl shadow-sm border border-gray-200">
            {tabs.filter(t => t.available).map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  activeTab === tab.id
                    ? 'bg-msu-green text-white shadow-sm'
                    : 'text-gray-600 hover:text-gray-800 hover:bg-gray-50'
                }`}
              >
                {tab.label}
                {tab.id === 'enhanced' && (
                  <span className="ml-1.5 px-1.5 py-0.5 text-[10px] font-bold uppercase rounded bg-white/20">
                    AI
                  </span>
                )}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            {activeTab === 'edited' && (
              <button
                onClick={handleSaveEdited}
                className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  editSaved
                    ? 'bg-emerald-100 text-emerald-700 border border-emerald-200'
                    : 'bg-white text-gray-700 border border-gray-200 hover:border-gray-300 shadow-sm'
                }`}
              >
                {editSaved ? 'Saved' : 'Save Changes'}
              </button>
            )}
            <button
              onClick={() => window.print()}
              className="px-5 py-2.5 bg-white text-gray-700 rounded-lg shadow-sm border border-gray-200 hover:border-gray-300 text-sm font-medium transition-all"
            >
              Export PDF
            </button>
          </div>
        </div>

        {activeTab !== 'original' && activeTab !== 'edited' && enhancedProfile && (
          <div className="mb-4 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-800 print:hidden">
            This resume has been enhanced with insights from your voice interview.
            New details, skills, and achievements discovered during the conversation have been merged in.
          </div>
        )}

        {activeTab === 'edited' && (
          <div className="mb-4 px-4 py-3 bg-blue-50 border border-blue-200 rounded-xl text-sm text-blue-800 print:hidden">
            Click any text field in the resume to edit. Click &quot;Save Changes&quot; when done.
          </div>
        )}

        {currentProfile && (
          <ProfileCard
            profile={currentProfile}
            editable={activeTab === 'edited'}
            onProfileChange={activeTab === 'edited' ? setEditedProfile : undefined}
          />
        )}

        <div className="flex justify-center gap-4 mt-8 print:hidden">
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
