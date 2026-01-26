'use client';

import { useState, useEffect, lazy, Suspense } from 'react';
import { useRouter } from 'next/navigation';
import { Question, getVisibleQuestions, getPhaseSteps } from '@/lib/questions';
import QuestionWrapper from '@/components/questionnaire/question-wrapper';
import TextInput from '@/components/questionnaire/text-input';
import MultipleChoice from '@/components/questionnaire/multiple-choice';
import ProgressIndicator from '@/components/questionnaire/progress-indicator';

// Lazy load VoiceInterview to avoid loading Rive on initial page load
const VoiceInterview = lazy(() => import('@/components/voice/voice-interview'));

// Demo answers for quick testing
const demoAnswers: Record<string, string> = {
  name: 'Marcus Washington',
  location: 'East Lansing, MI',
  lifeStage: 'student',
  primaryGoal: 'Landing a corporate finance role at a top investment bank after graduation, with a focus on sports and entertainment clients.',
  major: 'Finance with a minor in Sports Management',
  university: 'Michigan State University',
  jobTitle: 'Summer Analyst',
  company: 'Goldman Sachs',
  bigWin: 'Led a team project analyzing $50M in athlete endorsement deals, identifying undervalued opportunities that resulted in a 23% ROI improvement. Presented findings directly to senior partners.',
  academicHistory: "Dean's List all semesters, Presidential Scholarship recipient, completed CFA Level 1, led the MSU Investment Club portfolio team.",
  xFactorCategory: 'sports',
  xFactorDetail: 'Team Captain of D1 Football - led the team to a conference championship. Balanced 40+ hours/week of training with a 3.8 GPA.',
  xFactorLessons: 'Being captain taught me how to motivate diverse personalities, make quick decisions under pressure, and that preparation beats talent when talent is unprepared.',
  hardSkills: 'Excel/Financial Modeling, Python, Bloomberg Terminal, PowerPoint, SQL',
  softSkillsFriend: 'Relentless, Loyal, Clutch',
  softSkillsSelf: 'Disciplined, Strategic, Empathetic',
  legacyStatement: 'I want to help professional athletes build generational wealth and break the cycle of financial instability that affects 78% of NFL players within 3 years of retirement.',
  aestheticVibe: 'professional',
  socialLinks: 'linkedin.com/in/marcuswashington, twitter.com/mwash_finance',
};

// BASICS phase questions (keyboard input) - only 3 questions
// primaryGoal will be asked by the voice agent as the first question
const BASICS_QUESTION_IDS = ['name', 'location', 'lifeStage'];

type InterviewMode = 'basics' | 'resume-upload' | 'voice' | 'generating';

export default function QuestionnairePage() {
  const router = useRouter();
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
  const [isProcessingResume, setIsProcessingResume] = useState(false);
  const [processingError, setProcessingError] = useState<string | null>(null);

  // Fetch questions from API on mount
  useEffect(() => {
    async function loadQuestions() {
      try {
        const res = await fetch('/api/questions');
        const data = await res.json();
        setQuestions(data.questions);
      } catch (error) {
        console.error('Failed to load questions:', error);
      } finally {
        setLoading(false);
      }
    }
    loadQuestions();
  }, []);

  // Filter to only BASICS questions for keyboard phase
  const basicsQuestions = questions.filter(q => BASICS_QUESTION_IDS.includes(q.id));
  const visibleBasicsQuestions = getVisibleQuestions(basicsQuestions, answers);
  const currentQuestion = visibleBasicsQuestions[currentIndex];
  const progress = Math.round(((currentIndex + 1) / visibleBasicsQuestions.length) * 100);

  // Update current answer when question changes
  useEffect(() => {
    if (currentQuestion) {
      setCurrentAnswer(answers[currentQuestion.id] || '');
    }
  }, [currentIndex, currentQuestion, answers]);

  const handleNext = async (selectedValue?: string | unknown) => {
    // Use selectedValue if provided (from MultipleChoice), otherwise use currentAnswer
    // Check if selectedValue is actually a string (not an event object)
    const answerValue = (typeof selectedValue === 'string') ? selectedValue : currentAnswer;
    
    if (!answerValue.trim() && currentQuestion.type !== 'select') return;

    // Save answer
    const updatedAnswers = {
      ...answers,
      [currentQuestion.id]: answerValue
    };
    setAnswers(updatedAnswers);

    // Animate out
    setIsAnimating(true);

    // Check if this is the last BASICS question
    if (currentIndex === visibleBasicsQuestions.length - 1) {
      // All users go to resume upload step (optional)
      setTimeout(() => {
        setMode('resume-upload');
        setIsAnimating(false);
      }, 400);
      return;
    }

    // Move to next question after animation
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

  const handleAutofill = () => {
    if (currentQuestion && demoAnswers[currentQuestion.id]) {
      setCurrentAnswer(demoAnswers[currentQuestion.id]);
    }
  };

  // Handle voice interview completion
  const handleVoiceComplete = async (
    voiceAnswers: Record<string, string>,
    transcript: Array<{ role: string; text: string }>
  ) => {
    setMode('generating');

    try {
      // Use local proxy to avoid mixed content issues
      const response = await fetch(`/api/backend/generate-profile`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          basics_answers: answers,
          transcript: transcript,
        }),
      });

      const data = await response.json();

      if (data.success && data.profile) {
        // Store profile, transcript, and extracted features in sessionStorage
        sessionStorage.setItem('generatedProfile', JSON.stringify(data.profile));
        sessionStorage.setItem('interviewTranscript', JSON.stringify(transcript));
        if (data.extracted_features) {
          sessionStorage.setItem('extractedFeatures', JSON.stringify(data.extracted_features));
        }

        // Navigate to preview
        router.push('/profile/preview');
      } else {
        console.error('Profile generation failed:', data.error || data.detail);
        alert('Failed to generate profile. Please try again.');
        setMode('voice');
      }
    } catch (error) {
      console.error('Error generating profile:', error);
      alert('An error occurred. Please try again.');
      setMode('voice');
    }
  };

  // Loading state
  if (loading || (mode === 'basics' && !currentQuestion)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40">
        <p className="text-gray-600">Loading questions...</p>
      </div>
    );
  }

  // Resume upload mode (optional for all users)
  if (mode === 'resume-upload') {
    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        setResumeFile(file);
      }
    };

    const handleContinue = async () => {
      // Process resume if uploaded
      if (resumeFile || linkedinUrl.trim()) {
        setIsProcessingResume(true);
        setProcessingError(null);
        
        try {
          const formData = new FormData();
          if (resumeFile) {
            formData.append('file', resumeFile);
          }
          if (linkedinUrl.trim()) {
            formData.append('linkedin_url', linkedinUrl.trim());
          }
          
          const response = await fetch('/api/backend/process-resume', {
            method: 'POST',
            body: formData,
          });
          
          const data = await response.json();
          
          if (data.success && data.data) {
            // Store the extracted resume context
            setResumeContext(data.data);
            sessionStorage.setItem('resumeContext', JSON.stringify(data.data));
            console.log('Resume processed successfully:', data.data);
          } else {
            console.error('Resume processing failed:', data.error);
            setProcessingError(data.error || 'Failed to process resume');
            setIsProcessingResume(false);
            return; // Don't proceed if processing failed
          }
        } catch (error) {
          console.error('Error processing resume:', error);
          setProcessingError('Failed to connect to server. Please try again.');
          setIsProcessingResume(false);
          return;
        }
        
        setIsProcessingResume(false);
      }
      
      // Continue to voice interview
      setMode('voice');
    };

    const handleSkip = () => {
      // Skip resume upload, go directly to voice interview
      setResumeFile(null);
      setLinkedinUrl('');
      setMode('voice');
    };

    return (
      <div className="min-h-screen w-full bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40 flex flex-col">
        {/* Progress indicator */}
        <div className="w-full pt-8">
          <ProgressIndicator
            currentStep={1}
            totalSteps={5}
            steps={getPhaseSteps()}
          />
        </div>

        {/* Main content */}
        <div className="flex-1 flex items-center justify-center px-4 py-12">
          <div className="max-w-xl w-full space-y-8">
            {/* Title */}
            <div className="text-center space-y-3">
              <h1 className="text-4xl font-serif font-semibold text-gray-800">
                Before we progress, would you like to upload your resume and LinkedIn profile URL?
              </h1>
              <p className="text-lg text-gray-600">
                This helps us make your profile even better.
              </p>
            </div>

            {/* Upload section */}
            <div className="space-y-6">
              {/* File upload */}
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

              {/* LinkedIn input */}
              <div className="space-y-3">
                <label className="block text-sm font-medium text-gray-700">
                  LinkedIn Profile URL
                </label>
                <input
                  type="url"
                  value={linkedinUrl}
                  onChange={(e) => setLinkedinUrl(e.target.value)}
                  placeholder="https://linkedin.com/in/yourprofile"
                  className="w-full px-4 py-4 bg-white/50 backdrop-blur-sm border-2 border-gray-200 rounded-xl text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-msu-green-light transition-colors text-lg"
                />
              </div>
            </div>

            {/* Error message */}
            {processingError && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                {processingError}
              </div>
            )}

            {/* Action buttons */}
            <div className="flex flex-col items-center gap-4 pt-4">
              <button
                onClick={handleContinue}
                disabled={(!resumeFile && !linkedinUrl.trim()) || isProcessingResume}
                className="w-full max-w-sm px-8 py-4 bg-msu-green text-white rounded-full text-lg font-medium hover:bg-msu-green-light transition-all shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:shadow-lg flex items-center justify-center gap-2"
              >
                {isProcessingResume ? (
                  <>
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Processing resume...
                  </>
                ) : (
                  'Continue'
                )}
              </button>
              <button
                onClick={handleSkip}
                disabled={isProcessingResume}
                className="text-sm text-gray-500 hover:text-gray-700 transition-colors disabled:opacity-50"
              >
                Skip for now
              </button>
              <button
                onClick={() => {
                  setMode('basics');
                  setCurrentIndex(visibleBasicsQuestions.length - 1);
                }}
                disabled={isProcessingResume}
                className="text-sm text-gray-400 hover:text-gray-600 transition-colors disabled:opacity-50"
              >
                ← Back
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Voice interview mode
  if (mode === 'voice') {
    return (
      <Suspense
        fallback={
          <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40">
            <div className="text-center space-y-4">
              <div className="w-16 h-16 mx-auto rounded-full bg-gradient-to-br from-emerald-400 to-teal-400 animate-pulse"></div>
              <p className="text-gray-600">Preparing voice interview...</p>
            </div>
          </div>
        }
      >
        <VoiceInterview
          basicsAnswers={answers}
          resumeContext={resumeContext}
          onComplete={handleVoiceComplete}
        />
      </Suspense>
    );
  }

  // Generating profile state
  if (mode === 'generating') {
    return (
      <div className="min-h-screen w-full bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40 flex items-center justify-center">
        <div className="text-center space-y-12">
          {/* Pulsing AI Orb */}
          <div className="relative flex items-center justify-center">
            {/* Outer glow - large pulse */}
            <div className="absolute w-48 h-48 rounded-full bg-gradient-to-br from-emerald-200/40 to-teal-200/40 blur-3xl animate-pulse"></div>

            {/* Middle glow */}
            <div className="absolute w-32 h-32 rounded-full bg-gradient-to-br from-emerald-300/50 to-teal-300/50 blur-2xl animate-pulse" style={{ animationDelay: '0.5s' }}></div>

            {/* Core orb with shimmer */}
            <div className="relative w-24 h-24 rounded-full bg-gradient-to-br from-emerald-400 to-teal-400 shadow-2xl shadow-emerald-500/50 animate-pulse" style={{ animationDelay: '0.25s' }}></div>
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl font-serif font-semibold text-gray-800">
              Crafting your profile...
            </h2>
            <p className="text-lg text-gray-600">
              Our AI is analyzing your responses and creating something special
            </p>
            <p className="text-sm text-gray-500">
              This usually takes 5-10 seconds
            </p>
          </div>
        </div>
      </div>
    );
  }

  // BASICS phase - keyboard input
  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40 flex flex-col">
      {/* Admin button - demo only */}
      <a
        href="/admin"
        className="fixed top-4 right-4 px-4 py-2 bg-gray-800 text-white text-sm font-medium rounded-lg hover:bg-gray-700 transition-colors z-50"
      >
        admin
      </a>

      {/* Progress indicator */}
      <div className="w-full pt-8">
        <ProgressIndicator
          currentStep={0} // BASICS is always step 0
          totalSteps={5}
          steps={getPhaseSteps()}
        />
      </div>

      {/* Main question area */}
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

      {/* Footer progress text */}
      <div className="w-full pb-8 text-center space-y-3">
        <p className="text-sm text-gray-500">
          Question {currentIndex + 1} of {visibleBasicsQuestions.length} · {progress}% complete
        </p>
        {demoAnswers[currentQuestion.id] && (
          <button
            onClick={handleAutofill}
            className="text-xs px-3 py-1 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-full transition-colors"
          >
            Fill demo answer
          </button>
        )}

        {/* Voice interview preview hint */}
        {currentIndex === visibleBasicsQuestions.length - 1 && (
          <p className="text-xs text-msu-green-light mt-4">
            Next: Voice interview for deeper questions
          </p>
        )}
      </div>
    </div>
  );
}
