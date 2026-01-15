'use client';

import { ReactNode } from 'react';

interface QuestionWrapperProps {
  question: string;
  subtext?: string;
  children: ReactNode;
  onNext?: () => void;
  onBack?: () => void;
  showBack?: boolean;
  isAnimating?: boolean;
}

export default function QuestionWrapper({
  question,
  subtext,
  children,
  onNext,
  onBack,
  showBack = false,
  isAnimating = false
}: QuestionWrapperProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center w-full max-w-2xl mx-auto px-6 transition-all duration-500 ${
        isAnimating ? 'opacity-0 translate-y-4' : 'opacity-100 translate-y-0'
      }`}
    >
      <div className="text-center mb-12 space-y-4">
        <h1 className="text-5xl font-serif text-gray-800 leading-tight">
          {question}
        </h1>
        {subtext && (
          <p className="text-lg text-gray-600 max-w-xl mx-auto">
            {subtext}
          </p>
        )}
      </div>

      <div className="w-full max-w-xl">
        {children}
      </div>

      {showBack && (
        <button
          onClick={onBack}
          className="mt-8 text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          ← Back
        </button>
      )}
    </div>
  );
}
