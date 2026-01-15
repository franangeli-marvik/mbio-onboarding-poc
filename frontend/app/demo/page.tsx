'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { demoProfile } from '@/lib/demo-profile';

export default function DemoPage() {
  const router = useRouter();

  useEffect(() => {
    // Store demo profile in sessionStorage
    sessionStorage.setItem('generatedProfile', JSON.stringify(demoProfile));

    // Redirect to preview
    router.push('/profile/preview');
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40">
      <div className="text-center space-y-4">
        <div className="animate-spin w-12 h-12 border-4 border-msu-green border-t-transparent rounded-full mx-auto" />
        <p className="text-lg text-gray-600 font-medium">Loading demo profile...</p>
      </div>
    </div>
  );
}
