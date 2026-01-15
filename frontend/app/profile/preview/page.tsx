"use client";

import { useEffect, useState } from "react";
import ProfileCard from "@/components/profile/profile-card";
import { GeneratedProfile } from "@/lib/types";
import Link from "next/link";

export default function ProfilePreviewPage() {
  const [profile, setProfile] = useState<GeneratedProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Get profile from sessionStorage
    const profileData = sessionStorage.getItem("generatedProfile");

    if (profileData) {
      try {
        const parsed = JSON.parse(profileData);
        setProfile(parsed);
      } catch (err) {
        setError("Failed to load profile");
      }
    } else {
      setError("No profile data found");
    }

    setIsLoading(false);
  }, []);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40">
        <div className="text-center space-y-4">
          <div className="animate-spin w-12 h-12 border-4 border-msu-green border-t-transparent rounded-full mx-auto" />
          <p className="text-lg text-gray-600 font-medium">
            Generating your profile...
          </p>
          <p className="text-sm text-gray-500">This may take a few seconds</p>
        </div>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40">
        <div className="text-center space-y-4">
          <div className="text-red-600 text-6xl mb-4">⚠️</div>
          <h1 className="text-2xl font-semibold text-gray-900">
            {error || "Something went wrong"}
          </h1>
          <a
            href="/profile/new"
            className="inline-block px-6 py-3 bg-msu-green text-white rounded-full hover:bg-msu-green-light transition-colors"
          >
            Start Over
          </a>
        </div>
      </div>
    );
  }

  return (
    <div>
      <ProfileCard profile={profile} />

      {/* Action Buttons */}
      <div className="fixed bottom-8 right-8 flex gap-3 print:hidden">
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
  );
}
