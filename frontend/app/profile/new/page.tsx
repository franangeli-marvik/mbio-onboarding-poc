'use client';

import { useState, useEffect, useRef, useCallback, lazy, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Question, getVisibleQuestions, getPhaseSteps } from '@/lib/questions';
import QuestionWrapper from '@/components/questionnaire/question-wrapper';
import TextInput from '@/components/questionnaire/text-input';
import MultipleChoice from '@/components/questionnaire/multiple-choice';
import ProgressIndicator from '@/components/questionnaire/progress-indicator';

const VoiceInterview = lazy(() => import('@/components/voice/voice-interview'));

interface TenantPosition {
  id: string;
  title: string;
  focus_area: string;
}

interface TenantData {
  tenant_id: string;
  company_name: string;
  tone: string;
  positions: TenantPosition[];
}

const BASICS_QUESTION_IDS = ['name', 'location'];

type InterviewMode = 'basics' | 'position-select' | 'resume-upload' | 'pipeline-loading' | 'voice' | 'enhancing';

const PIPELINE_STEPS = [
  'Parsing resume...',
  'Analyzing profile...',
  'Planning questions...',
  'Preparing interview...',
];
const STEP_INTERVAL_MS = 10_000;

export default function QuestionnairePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40">
        <p className="text-gray-600">Loading...</p>
      </div>
    }>
      <QuestionnaireContent />
    </Suspense>
  );
}

function QuestionnaireContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tenantId = searchParams.get('tenant') || 'default';

  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [currentAnswer, setCurrentAnswer] = useState('');
  const [isAnimating, setIsAnimating] = useState(false);
  const [mode, setMode] = useState<InterviewMode>('basics');
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [linkedinUrl, setLinkedinUrl] = useState('');
  const [resumeContext, setResumeContext] = useState<Record<string, unknown> | null>(null);
  const [processingError, setProcessingError] = useState<string | null>(null);

  const [interviewBriefing, setInterviewBriefing] = useState<Record<string, unknown> | null>(null);
  const [interviewPlan, setInterviewPlan] = useState<Record<string, unknown> | null>(null);
  const [tenantData, setTenantData] = useState<TenantData | null>(null);
  const [selectedPositionId, setSelectedPositionId] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [questionsRes, tenantRes] = await Promise.all([
          fetch('/api/questions'),
          fetch(`/api/backend/tenant/${tenantId}`),
        ]);
        const questionsData = await questionsRes.json();
        setQuestions(questionsData.questions);

        if (tenantRes.ok) {
          const tenant = await tenantRes.json();
          setTenantData(tenant);
        }
      } catch (error) {
        console.error('Failed to load initial data:', error);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [tenantId]);

  const basicsQuestions = questions.filter(q => BASICS_QUESTION_IDS.includes(q.id));
  const visibleBasicsQuestions = getVisibleQuestions(basicsQuestions, answers);
  const currentQuestion = visibleBasicsQuestions[currentIndex];
  const progress = Math.round(((currentIndex + 1) / visibleBasicsQuestions.length) * 100);

  useEffect(() => {
    if (currentQuestion) {
      setCurrentAnswer(answers[currentQuestion.id] || '');
    }
  }, [currentIndex, currentQuestion, answers]);

  const handleNext = async (selectedValue?: string | unknown) => {
    const answerValue = (typeof selectedValue === 'string') ? selectedValue : currentAnswer;
    if (!answerValue.trim() && currentQuestion.type !== 'select') return;

    const updatedAnswers = {
      ...answers,
      [currentQuestion.id]: answerValue,
    };
    setAnswers(updatedAnswers);

    setIsAnimating(true);

    if (currentIndex === visibleBasicsQuestions.length - 1) {
      setTimeout(() => {
        setMode('position-select');
        setIsAnimating(false);
      }, 400);
      return;
    }

    setTimeout(() => {
      setCurrentIndex(prev => prev + 1);
      setIsAnimating(false);
    }, 300);
  };

  const handleBack = () => {
    if (currentIndex === 0) return;
    setIsAnimating(true);
    setTimeout(() => {
      setCurrentIndex(prev => prev - 1);
      setIsAnimating(false);
    }, 300);
  };

  const handleVoiceComplete = (
    _voiceAnswers: Record<string, string>,
    transcript: Array<{ role: string; text: string }>
  ) => {
    sessionStorage.setItem('interviewTranscript', JSON.stringify(transcript));
    setMode('enhancing');
  };

  if (loading || (mode === 'basics' && !currentQuestion)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40">
        <p className="text-gray-600">Loading...</p>
      </div>
    );
  }

  if (mode === 'position-select') {
    const positions = tenantData?.positions || [];
    const companyName = tenantData?.company_name || 'M.bio';

    const handlePositionSelect = (positionId: string) => {
      setSelectedPositionId(positionId);
      setTimeout(() => {
        setMode('resume-upload');
      }, 300);
    };

    return (
      <div className="min-h-screen w-full bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40 flex flex-col">
        <div className="w-full pt-8">
          <ProgressIndicator
            currentStep={1}
            totalSteps={5}
            steps={getPhaseSteps()}
          />
        </div>

        <div className="flex-1 flex items-center justify-center px-4 py-12">
          <div className="max-w-xl w-full space-y-8">
            <div className="text-center space-y-3">
              <h1 className="text-4xl font-serif font-semibold text-gray-800">
                Which position are you applying for?
              </h1>
              <p className="text-lg text-gray-600">
                Select the role at {companyName} that best matches your profile.
              </p>
            </div>

            <div className="grid gap-3 w-full">
              {positions.map((position) => (
                <button
                  key={position.id}
                  onClick={() => handlePositionSelect(position.id)}
                  className={`
                    px-6 py-5 text-left rounded-2xl border-2 transition-all duration-300
                    ${selectedPositionId === position.id
                      ? 'bg-msu-green text-white border-msu-green shadow-lg scale-[1.02]'
                      : 'bg-white/50 backdrop-blur-sm text-gray-800 border-gray-200 hover:border-msu-green-light hover:shadow-md'
                    }
                  `}
                >
                  <span className="text-lg font-medium block">{position.title}</span>
                  <span className={`text-sm mt-1 block ${
                    selectedPositionId === position.id ? 'text-white/80' : 'text-gray-500'
                  }`}>
                    {position.focus_area}
                  </span>
                </button>
              ))}
            </div>

            <div className="flex justify-center pt-4">
              <button
                onClick={() => {
                  setMode('basics');
                  setCurrentIndex(visibleBasicsQuestions.length - 1);
                }}
                className="text-sm text-gray-400 hover:text-gray-600 transition-colors"
              >
                &larr; Back
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (mode === 'resume-upload') {
    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        setResumeFile(file);
      }
    };

    const handleContinue = () => {
      if (!resumeFile) return;
      setMode('pipeline-loading');
    };

    return (
      <div className="min-h-screen w-full bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40 flex flex-col">
        <div className="w-full pt-8">
          <ProgressIndicator
            currentStep={2}
            totalSteps={5}
            steps={getPhaseSteps()}
          />
        </div>

        <div className="flex-1 flex items-center justify-center px-4 py-12">
          <div className="max-w-xl w-full space-y-8">
            <div className="text-center space-y-3">
              <h1 className="text-4xl font-serif font-semibold text-gray-800">
                Upload your resume
              </h1>
              <p className="text-lg text-gray-600">
                We'll use it to personalize your interview experience.
              </p>
            </div>

            <div className="space-y-6">
              <div className="space-y-3">
                <label className="block text-sm font-medium text-gray-700">
                  Resume / CV
                </label>
                <div
                  className={`relative border-2 border-dashed rounded-2xl p-8 text-center transition-all cursor-pointer hover:border-msu-green-light hover:bg-white/50 ${
                    resumeFile ? 'border-msu-green bg-emerald-50/50' : 'border-gray-300'
                  }`}
                  onClick={() => document.getElementById('resume-input')?.click()}
                >
                  <input
                    id="resume-input"
                    type="file"
                    accept=".pdf,.doc,.docx"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  {resumeFile ? (
                    <div className="space-y-2">
                      <div className="w-12 h-12 mx-auto rounded-full bg-msu-green/10 flex items-center justify-center">
                        <svg className="w-6 h-6 text-msu-green" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                      <p className="text-gray-800 font-medium">{resumeFile.name}</p>
                      <p className="text-sm text-gray-500">Click to change file</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="w-12 h-12 mx-auto rounded-full bg-gray-100 flex items-center justify-center">
                        <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                      </div>
                      <p className="text-gray-600">Drop your resume here or click to browse</p>
                      <p className="text-sm text-gray-400">PDF, DOC, or DOCX</p>
                    </div>
                  )}
                </div>
              </div>

            </div>

            {processingError && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                {processingError}
              </div>
            )}

            <div className="flex flex-col items-center gap-4 pt-4">
              <button
                onClick={handleContinue}
                disabled={!resumeFile}
                className="w-full max-w-sm px-8 py-4 bg-msu-green text-white rounded-full text-lg font-medium hover:bg-msu-green-light transition-all shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:shadow-lg"
              >
                Continue
              </button>
              <button
                onClick={() => setMode('position-select')}
                className="text-sm text-gray-400 hover:text-gray-600 transition-colors"
              >
                &larr; Back
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (mode === 'pipeline-loading') {
    return (
      <PipelineLoadingScreen
        resumeFile={resumeFile!}
        tenantId={tenantId}
        positionId={selectedPositionId || ''}
        linkedinUrl={linkedinUrl}
        onComplete={(data) => {
          if (data.resume_data) {
            setResumeContext(data.resume_data as Record<string, unknown>);
            sessionStorage.setItem('resumeContext', JSON.stringify(data.resume_data));
          }
          if (data.interview_briefing) {
            setInterviewBriefing(data.interview_briefing as Record<string, unknown>);
            sessionStorage.setItem('interviewBriefing', JSON.stringify(data.interview_briefing));
          }
          if (data.profile_analysis) {
            sessionStorage.setItem('profileAnalysis', JSON.stringify(data.profile_analysis));
          }
          if (data.interview_plan) {
            setInterviewPlan(data.interview_plan as Record<string, unknown>);
            sessionStorage.setItem('interviewPlan', JSON.stringify(data.interview_plan));
          }
          setMode('voice');
        }}
        onError={(error) => {
          setProcessingError(error);
          setMode('resume-upload');
        }}
      />
    );
  }

  if (mode === 'voice') {
    return (
      <Suspense
        fallback={
          <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40">
            <div className="text-center space-y-4">
              <div className="w-16 h-16 mx-auto rounded-full bg-gradient-to-br from-emerald-400 to-teal-400 animate-pulse" />
              <p className="text-gray-600">Preparing voice interview...</p>
            </div>
          </div>
        }
      >
        <VoiceInterview
          basicsAnswers={answers}
          resumeContext={resumeContext}
          interviewBriefing={interviewBriefing}
          interviewPlan={interviewPlan}
          onComplete={handleVoiceComplete}
        />
      </Suspense>
    );
  }

  if (mode === 'enhancing') {
    return (
      <EnhancingScreen
        answers={answers}
        onComplete={() => router.push('/profile/preview')}
        onError={(error) => {
          console.error('Enhancement failed:', error);
          router.push('/profile/preview');
        }}
      />
    );
  }

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40 flex flex-col">
      <div className="w-full pt-8">
        <ProgressIndicator
          currentStep={0}
          totalSteps={5}
          steps={getPhaseSteps()}
        />
      </div>

      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <QuestionWrapper
          question={currentQuestion.question}
          subtext={currentQuestion.subtext}
          onNext={handleNext}
          onBack={handleBack}
          showBack={currentIndex > 0}
          isAnimating={isAnimating}
        >
          {currentQuestion.type === 'select' && currentQuestion.options ? (
            <MultipleChoice
              options={currentQuestion.options}
              value={currentAnswer}
              onChange={setCurrentAnswer}
              onSubmit={handleNext}
            />
          ) : currentQuestion.type === 'textarea' ? (
            <TextInput
              value={currentAnswer}
              onChange={setCurrentAnswer}
              onSubmit={handleNext}
              placeholder={currentQuestion.placeholder}
              multiline
            />
          ) : (
            <TextInput
              value={currentAnswer}
              onChange={setCurrentAnswer}
              onSubmit={handleNext}
              placeholder={currentQuestion.placeholder}
            />
          )}
        </QuestionWrapper>
      </div>

      <div className="w-full pb-8 text-center">
        <p className="text-sm text-gray-500">
          Question {currentIndex + 1} of {visibleBasicsQuestions.length} &middot; {progress}% complete
        </p>
      </div>
    </div>
  );
}


interface PipelineLoadingScreenProps {
  resumeFile: File;
  tenantId: string;
  positionId: string;
  linkedinUrl: string;
  onComplete: (data: Record<string, unknown>) => void;
  onError: (error: string) => void;
}

function PipelineLoadingScreen({
  resumeFile,
  tenantId,
  positionId,
  linkedinUrl,
  onComplete,
  onError,
}: PipelineLoadingScreenProps) {
  const [activeStep, setActiveStep] = useState(0);
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [done, setDone] = useState(false);
  const called = useRef(false);

  const handleComplete = useCallback(onComplete, [onComplete]);
  const handleError = useCallback(onError, [onError]);

  useEffect(() => {
    if (called.current) return;
    called.current = true;

    const timers: ReturnType<typeof setTimeout>[] = [];

    for (let i = 1; i < PIPELINE_STEPS.length; i++) {
      timers.push(
        setTimeout(() => {
          setCompletedSteps(prev => [...prev, i - 1]);
          setActiveStep(i);
        }, i * STEP_INTERVAL_MS)
      );
    }

    const formData = new FormData();
    formData.append('file', resumeFile);
    formData.append('tenant_id', tenantId);
    formData.append('position_id', positionId);
    if (linkedinUrl.trim()) {
      formData.append('linkedin_url', linkedinUrl.trim());
    }

    fetch('/api/backend/process-resume', {
      method: 'POST',
      body: formData,
    })
      .then(res => res.json())
      .then(data => {
        timers.forEach(clearTimeout);

        const allIdxs = PIPELINE_STEPS.map((_, i) => i);
        setCompletedSteps(allIdxs);
        setActiveStep(PIPELINE_STEPS.length);
        setDone(true);

        setTimeout(() => {
          if (data.success) {
            handleComplete(data);
          } else {
            handleError(data.error || 'Pipeline failed');
          }
        }, 800);
      })
      .catch(() => {
        timers.forEach(clearTimeout);
        handleError('Failed to connect to server. Please try again.');
      });

    return () => timers.forEach(clearTimeout);
  }, [resumeFile, tenantId, positionId, linkedinUrl, handleComplete, handleError]);

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40 flex flex-col">
      <div className="w-full pt-8">
        <ProgressIndicator
          currentStep={2}
          totalSteps={5}
          steps={getPhaseSteps()}
        />
      </div>

      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="max-w-md w-full space-y-12">
          <div className="relative flex items-center justify-center">
            <div className="absolute w-48 h-48 rounded-full bg-gradient-to-br from-emerald-200/40 to-teal-200/40 blur-3xl animate-pulse" />
            <div className="absolute w-32 h-32 rounded-full bg-gradient-to-br from-emerald-300/50 to-teal-300/50 blur-2xl animate-pulse" style={{ animationDelay: '0.5s' }} />
            <div className={`relative w-24 h-24 rounded-full bg-gradient-to-br from-emerald-400 to-teal-400 shadow-2xl shadow-emerald-500/50 ${done ? '' : 'animate-pulse'}`} style={{ animationDelay: '0.25s' }} />
          </div>

          <div className="text-center space-y-2">
            <h2 className="text-2xl font-serif font-semibold text-gray-800">
              {done ? 'Ready!' : 'Preparing your interview...'}
            </h2>
            <p className="text-sm text-gray-500">
              {done ? 'Moving to the next step' : 'This usually takes about 45 seconds'}
            </p>
          </div>

          <div className="space-y-4">
            {PIPELINE_STEPS.map((label, idx) => {
              const isCompleted = completedSteps.includes(idx);
              const isActive = activeStep === idx && !isCompleted;

              return (
                <div key={idx} className="flex items-center gap-4">
                  <div className={`
                    w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-500
                    ${isCompleted
                      ? 'bg-msu-green text-white'
                      : isActive
                        ? 'bg-msu-green/20 border-2 border-msu-green'
                        : 'bg-gray-100 border-2 border-gray-200'
                    }
                  `}>
                    {isCompleted ? (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : isActive ? (
                      <div className="w-3 h-3 rounded-full bg-msu-green animate-pulse" />
                    ) : (
                      <span className="text-xs text-gray-400 font-medium">{idx + 1}</span>
                    )}
                  </div>
                  <span className={`text-lg transition-colors duration-300 ${
                    isCompleted ? 'text-gray-800 font-medium' : isActive ? 'text-gray-700' : 'text-gray-400'
                  }`}>
                    {label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}


interface EnhancingScreenProps {
  answers: Record<string, string>;
  onComplete: () => void;
  onError: (error: string) => void;
}

function EnhancingScreen({ answers, onComplete, onError }: EnhancingScreenProps) {
  const called = useRef(false);

  const handleComplete = useCallback(onComplete, [onComplete]);
  const handleError = useCallback(onError, [onError]);

  useEffect(() => {
    if (called.current) return;
    called.current = true;

    const resumeRaw = sessionStorage.getItem('resumeContext');
    const transcriptRaw = sessionStorage.getItem('interviewTranscript');
    const analysisRaw = sessionStorage.getItem('profileAnalysis');

    if (!resumeRaw || !transcriptRaw) {
      handleComplete();
      return;
    }

    const body = {
      resume_data: JSON.parse(resumeRaw),
      transcript: JSON.parse(transcriptRaw),
      profile_analysis: analysisRaw ? JSON.parse(analysisRaw) : null,
      basics_answers: answers,
    };

    fetch('/api/backend/enhance-resume', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          sessionStorage.setItem('originalProfile', JSON.stringify(data.original));
          sessionStorage.setItem('enhancedProfile', JSON.stringify(data.enhanced));
        }
        setTimeout(handleComplete, 600);
      })
      .catch((err) => {
        console.error('Enhancement API error:', err);
        handleError(err.message || 'Enhancement failed');
      });
  }, [answers, handleComplete, handleError]);

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40 flex flex-col">
      <div className="w-full pt-8">
        <ProgressIndicator
          currentStep={4}
          totalSteps={5}
          steps={getPhaseSteps()}
        />
      </div>

      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="max-w-md w-full space-y-12 text-center">
          <div className="relative flex items-center justify-center">
            <div className="absolute w-48 h-48 rounded-full bg-gradient-to-br from-emerald-200/40 to-teal-200/40 blur-3xl animate-pulse" />
            <div className="absolute w-32 h-32 rounded-full bg-gradient-to-br from-emerald-300/50 to-teal-300/50 blur-2xl animate-pulse" style={{ animationDelay: '0.5s' }} />
            <div className="relative w-24 h-24 rounded-full bg-gradient-to-br from-emerald-400 to-teal-400 shadow-2xl shadow-emerald-500/50 animate-pulse" style={{ animationDelay: '0.25s' }} />
          </div>

          <div className="space-y-3">
            <h2 className="text-2xl font-serif font-semibold text-gray-800">
              Enhancing your resume...
            </h2>
            <p className="text-gray-500">
              Merging interview insights with your original resume
            </p>
          </div>

          <div className="space-y-3">
            {['Analyzing interview responses', 'Enriching experience details', 'Generating enhanced resume'].map((step, i) => (
              <div key={i} className="flex items-center gap-3 justify-center">
                <div className="w-2 h-2 rounded-full bg-msu-green animate-pulse" style={{ animationDelay: `${i * 0.3}s` }} />
                <span className="text-sm text-gray-600">{step}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
