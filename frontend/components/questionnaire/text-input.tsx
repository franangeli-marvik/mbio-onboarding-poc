'use client';

import { useState } from 'react';

interface TextInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  placeholder?: string;
  multiline?: boolean;
  autoFocus?: boolean;
}

export default function TextInput({
  value,
  onChange,
  onSubmit,
  placeholder = "Type your answer...",
  multiline = false,
  autoFocus = true
}: TextInputProps) {
  const [isFocused, setIsFocused] = useState(false);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !multiline) {
      e.preventDefault();
      if (value.trim()) {
        onSubmit();
      }
    }
  };

  const inputClasses = `
    w-full px-6 py-4
    text-lg text-gray-800
    bg-white/50 backdrop-blur-sm
    border-2 rounded-2xl
    transition-all duration-300
    focus:outline-none focus:ring-0
    placeholder:text-gray-400
    ${isFocused
      ? 'border-msu-green-light shadow-lg shadow-msu-green-light/20'
      : 'border-gray-200 hover:border-gray-300'
    }
  `;

  return (
    <div className="relative w-full">
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={placeholder}
          autoFocus={autoFocus}
          rows={4}
          className={`${inputClasses} resize-none`}
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={placeholder}
          autoFocus={autoFocus}
          className={inputClasses}
        />
      )}

      {value.trim() && (
        <button
          onClick={onSubmit}
          className="absolute right-3 top-1/2 -translate-y-1/2
                     w-10 h-10 rounded-full
                     bg-msu-green hover:bg-msu-green-light
                     text-white
                     transition-all duration-300
                     flex items-center justify-center
                     shadow-md hover:shadow-lg"
          aria-label="Submit answer"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M10 4L10 16M10 4L6 8M10 4L14 8"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      )}
    </div>
  );
}
