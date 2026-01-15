'use client';

interface Option {
  value: string;
  label: string;
}

interface MultipleChoiceProps {
  options: Option[];
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export default function MultipleChoice({
  options,
  value,
  onChange,
  onSubmit
}: MultipleChoiceProps) {
  const handleSelect = (optionValue: string) => {
    onChange(optionValue);
    // Auto-submit after a brief delay for smooth UX
    setTimeout(() => {
      onSubmit();
    }, 300);
  };

  return (
    <div className="grid gap-3 w-full">
      {options.map((option) => (
        <button
          key={option.value}
          onClick={() => handleSelect(option.value)}
          className={`
            px-6 py-4
            text-left text-lg
            rounded-2xl
            border-2
            transition-all duration-300
            ${value === option.value
              ? 'bg-msu-green text-white border-msu-green shadow-lg scale-[1.02]'
              : 'bg-white/50 backdrop-blur-sm text-gray-800 border-gray-200 hover:border-msu-green-light hover:shadow-md'
            }
          `}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
