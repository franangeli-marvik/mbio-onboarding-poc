'use client';

interface ProgressIndicatorProps {
  currentStep: number;
  totalSteps: number;
  steps: string[];
}

export default function ProgressIndicator({
  currentStep,
  totalSteps,
  steps
}: ProgressIndicatorProps) {
  return (
    <div className="flex items-center justify-center gap-3 py-6">
      {steps.map((step, index) => (
        <div key={step} className="flex items-center gap-3">
          <div className="flex flex-col items-center gap-1">
            <div
              className={`h-2 w-2 rounded-full transition-all duration-300 ${
                index < currentStep
                  ? 'bg-msu-green scale-110'
                  : index === currentStep
                  ? 'bg-msu-green-light scale-125'
                  : 'bg-gray-300'
              }`}
            />
            <span
              className={`text-xs font-medium transition-all duration-300 ${
                index === currentStep
                  ? 'text-msu-green'
                  : 'text-gray-400'
              }`}
            >
              {step}
            </span>
          </div>
          {index < steps.length - 1 && (
            <div
              className={`h-px w-12 transition-all duration-300 ${
                index < currentStep ? 'bg-msu-green' : 'bg-gray-300'
              }`}
            />
          )}
        </div>
      ))}
    </div>
  );
}
