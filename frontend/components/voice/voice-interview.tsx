'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Persona, PersonaState } from '@/components/ai-elements/persona';
import ProgressIndicator from '@/components/questionnaire/progress-indicator';
import { Room, RoomEvent, ConnectionState, Track, RemoteTrack, RemoteParticipant, LocalParticipant, TranscriptionSegment } from 'livekit-client';
import { getToken } from '@/lib/livekit';

interface VoiceInterviewProps {
  basicsAnswers: Record<string, string>;
  onComplete: (voiceAnswers: Record<string, string>, transcript: Array<{ role: string; text: string }>) => void;
}

type Phase = 'school' | 'life' | 'skills' | 'impact';
const PHASES: Phase[] = ['school', 'life', 'skills', 'impact'];
const PHASE_LABELS = ['SCHOOL', 'LIFE', 'SKILLS', 'IMPACT'];

type VoiceState = 'connecting' | 'listening' | 'thinking' | 'speaking' | 'idle' | 'error';

export default function VoiceInterview({ basicsAnswers, onComplete }: VoiceInterviewProps) {
  const router = useRouter();
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [isConnected, setIsConnected] = useState(false);
  const [agentText, setAgentText] = useState('');
  const [userText, setUserText] = useState('');
  const [transcript, setTranscript] = useState<Array<{ role: string; text: string; timestamp: string }>>([]);
  const [showIntro, setShowIntro] = useState(true);
  const [noteText, setNoteText] = useState('');
  const [currentPhase, setCurrentPhase] = useState(0);
  const [error, setError] = useState<string | null>(null);
  
  const roomRef = useRef<Room | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const participantName = basicsAnswers.name || 'User';

  // Map voice state to persona state
  const getPersonaState = (): PersonaState => {
    switch (voiceState) {
      case 'listening':
        return 'listening';
      case 'thinking':
        return 'thinking';
      case 'speaking':
        return 'speaking';
      case 'connecting':
        return 'thinking';
      default:
        return 'idle';
    }
  };

  // Generate unique room name
  const generateRoomName = () => {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 8);
    return `interview-${timestamp}-${random}`;
  };

  // Connect to LiveKit room
  const connectToRoom = useCallback(async () => {
    try {
      setVoiceState('connecting');
      setError(null);

      const roomName = generateRoomName();
      
      // Get token from backend
      const { token, url } = await getToken(roomName, participantName);

      // Create room
      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
        audioCaptureDefaults: {
          autoGainControl: true,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      roomRef.current = room;

      // Set up event listeners BEFORE connecting
      room.on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
        console.log('Connection state:', state);
        if (state === ConnectionState.Connected) {
          setIsConnected(true);
          setVoiceState('listening');
        } else if (state === ConnectionState.Disconnected) {
          setIsConnected(false);
          setVoiceState('idle');
        }
      });

      // Handle agent audio track
      room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack, publication, participant: RemoteParticipant) => {
        console.log('Track subscribed:', track.kind, 'from', participant.identity);
        
        if (track.kind === Track.Kind.Audio) {
          setVoiceState('speaking');
          
          // Create audio element and play
          const audioElement = track.attach();
          audioElement.id = 'agent-audio';
          document.body.appendChild(audioElement);
          audioElementRef.current = audioElement;
          audioElement.play().catch(console.error);
        }
      });

      room.on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
        console.log('Track unsubscribed:', track.kind);
        if (track.kind === Track.Kind.Audio) {
          track.detach().forEach(el => el.remove());
          setVoiceState('listening');
        }
      });

      // Handle LiveKit's built-in transcription events
      room.on(RoomEvent.TranscriptionReceived, (segments: TranscriptionSegment[], participant) => {
        console.log('Transcription received:', segments, 'from:', participant?.identity);
        
        for (const segment of segments) {
          const isAgent = participant?.identity?.includes('agent') || !participant?.identity?.startsWith(participantName);
          const role = isAgent ? 'agent' : 'user';
          const text = segment.text;
          const isFinal = segment.final;
          
          console.log(`[${role}] ${isFinal ? 'FINAL' : 'partial'}: ${text}`);
          
          if (role === 'agent') {
            setAgentText(text);
            if (isFinal && text.trim()) {
              setTranscript(prev => [...prev, {
                role: 'agent',
                text,
                timestamp: new Date().toISOString()
              }]);
              
              // Detect phase from agent's speech
              const textLower = text.toLowerCase();
              if (textLower.includes('impact') || textLower.includes('legacy') || textLower.includes('difference')) {
                setCurrentPhase(3); // IMPACT
              } else if (textLower.includes('skill') || textLower.includes('technical') || textLower.includes('programming')) {
                setCurrentPhase(2); // SKILLS
              } else if (textLower.includes('achievement') || textLower.includes('proud') || textLower.includes('interest') || textLower.includes('hobby')) {
                setCurrentPhase(1); // LIFE
              }
            }
          } else {
            setUserText(text);
            if (isFinal && text.trim()) {
              setTranscript(prev => [...prev, {
                role: 'user',
                text,
                timestamp: new Date().toISOString()
              }]);
              setUserText('');
            }
          }
        }
      });

      // Handle custom data messages (user notes, phase updates from agent)
      room.on(RoomEvent.DataReceived, (payload: Uint8Array, participant) => {
        try {
          const data = JSON.parse(new TextDecoder().decode(payload));
          console.log('Data received:', data);
          
          // Handle phase updates from agent
          if (data.phase) {
            const phaseIndex = PHASES.indexOf(data.phase as Phase);
            if (phaseIndex !== -1) {
              console.log('Phase changed to:', data.phase, 'index:', phaseIndex);
              setCurrentPhase(phaseIndex);
            }
          }
          
          // Handle manual transcripts (fallback)
          if (data.type === 'transcript') {
            const text = data.text;
            const role = data.role;
            const isFinal = data.is_final !== false;
            
            if (role === 'agent' && isFinal && text?.trim()) {
              setAgentText(text);
              setTranscript(prev => [...prev, {
                role: 'agent',
                text,
                timestamp: new Date().toISOString()
              }]);
            }
          }
        } catch (e) {
          // Ignore non-JSON data
        }
      });

      // Handle participant events
      room.on(RoomEvent.ParticipantConnected, (participant) => {
        console.log('Participant connected:', participant.identity);
      });

      // Connect to room
      await room.connect(url, token);
      console.log('Connected to room:', roomName);

      // Enable microphone immediately for continuous conversation
      await room.localParticipant.setMicrophoneEnabled(true);
      console.log('Microphone enabled');

      setVoiceState('listening');

    } catch (error) {
      console.error('Failed to connect:', error);
      setError(error instanceof Error ? error.message : 'Failed to connect');
      setVoiceState('error');
    }
  }, [participantName]);

  // Disconnect from room
  const disconnect = useCallback(async () => {
    if (roomRef.current) {
      await roomRef.current.disconnect();
      roomRef.current = null;
    }
    if (audioElementRef.current) {
      audioElementRef.current.remove();
      audioElementRef.current = null;
    }
    setIsConnected(false);
    setVoiceState('idle');
  }, []);

  // Handle interview completion
  const handleComplete = useCallback(async () => {
    await disconnect();
    
    // Combine transcript into answers
    const voiceAnswers: Record<string, string> = {};
    
    // Extract answers from transcript (simplified - the backend will do better extraction)
    const userMessages = transcript.filter(t => t.role === 'user').map(t => t.text);
    if (userMessages.length > 0) {
      voiceAnswers.interviewTranscript = userMessages.join('\n\n');
    }
    
    // Add any notes
    if (noteText.trim()) {
      voiceAnswers.additionalNotes = noteText;
    }

    onComplete(voiceAnswers, transcript);
  }, [disconnect, transcript, noteText, onComplete]);

  // Start voice interview
  const handleStartInterview = async () => {
    setShowIntro(false);
    await connectToRoom();
  };

  // Handle adding a note - send to agent via data channel
  const handleAddNote = async () => {
    if (noteText.trim() && roomRef.current) {
      const note = noteText.trim();
      
      // Add to local transcript
      setTranscript(prev => [...prev, {
        role: 'user',
        text: note,
        timestamp: new Date().toISOString()
      }]);
      
      // Send to agent via data channel so it can see/respond to it
      try {
        const encoder = new TextEncoder();
        const data = encoder.encode(JSON.stringify({
          type: 'user_note',
          text: note,
          timestamp: new Date().toISOString()
        }));
        await roomRef.current.localParticipant.publishData(data, { reliable: true });
        console.log('Note sent to agent:', note);
      } catch (e) {
        console.error('Failed to send note to agent:', e);
      }
      
      setNoteText('');
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  // Intro screen
  if (showIntro) {
    return (
      <div className="min-h-screen w-full bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40 flex flex-col items-center justify-center p-4">
        <div className="max-w-xl text-center space-y-8">
          <div className="w-32 h-32 mx-auto">
            <Persona state="idle" variant="obsidian" className="w-full h-full" />
          </div>

          <div className="space-y-4">
            <h1 className="text-4xl font-serif font-semibold text-gray-800">
              Ready for your interview, {basicsAnswers.name?.split(' ')[0] || 'there'}?
            </h1>
            <p className="text-lg text-gray-600">
              I'll ask you about your goals, experiences, skills, and aspirations.
              Just speak naturally - no need to press any buttons.
            </p>
            <p className="text-sm text-gray-500">
              You can also type notes if you want to add specific details.
            </p>
          </div>

          <div className="flex flex-col gap-4 max-w-sm mx-auto">
            <button
              onClick={handleStartInterview}
              className="px-8 py-4 bg-msu-green text-white rounded-full text-lg font-medium hover:bg-msu-green-light transition-all shadow-lg hover:shadow-xl flex items-center justify-center gap-3"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
              Start Interview
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (voiceState === 'error') {
    return (
      <div className="min-h-screen w-full bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40 flex flex-col items-center justify-center p-4">
        <div className="max-w-xl text-center space-y-6">
          <div className="w-24 h-24 mx-auto rounded-full bg-red-100 flex items-center justify-center">
            <svg className="w-12 h-12 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-2xl font-serif font-semibold text-gray-800">
            Connection Error
          </h2>
          <p className="text-gray-600">{error || 'Failed to connect to voice service'}</p>
          <button
            onClick={handleStartInterview}
            className="px-6 py-3 bg-msu-green text-white rounded-full font-medium hover:bg-msu-green-light transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  // Main interview UI
  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40 flex flex-col">
      {/* Progress indicator */}
      <div className="w-full pt-8">
        <ProgressIndicator
          currentStep={currentPhase + 1}
          totalSteps={5}
          steps={['BASICS', ...PHASE_LABELS]}
        />
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-8">
        <div className="w-full max-w-2xl mx-auto">
          {/* Persona avatar */}
          <div className="flex justify-center mb-8">
            <div className="relative">
              <div className="w-32 h-32">
                <Persona
                  state={getPersonaState()}
                  variant="obsidian"
                  className="w-full h-full"
                />
              </div>
              
              {/* Connection status indicator */}
              <div className={`absolute -bottom-2 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-xs font-medium ${
                isConnected 
                  ? 'bg-green-100 text-green-700' 
                  : voiceState === 'connecting'
                  ? 'bg-yellow-100 text-yellow-700'
                  : 'bg-gray-100 text-gray-600'
              }`}>
                {voiceState === 'connecting' ? 'Connecting...' :
                 voiceState === 'speaking' ? '🔊 Speaking' :
                 voiceState === 'listening' ? '🎤 Listening' :
                 voiceState === 'thinking' ? '💭 Thinking' :
                 'Ready'}
              </div>
            </div>
          </div>

          {/* Agent transcript (what the agent is saying) */}
          {agentText && (
            <div className="mb-6 p-4 bg-white/60 backdrop-blur-sm rounded-2xl border border-gray-200 transition-all">
              <p className="text-gray-700 text-lg leading-relaxed">{agentText}</p>
            </div>
          )}

          {/* User transcript (what user is saying) */}
          {userText && (
            <div className="mb-6 p-4 bg-msu-green/10 backdrop-blur-sm rounded-2xl border border-msu-green/20 transition-all">
              <p className="text-sm text-msu-green-light mb-1">You:</p>
              <p className="text-gray-800">{userText}</p>
            </div>
          )}

          {/* Conversation history - hidden, only used for profile generation */}

          {/* Notes input (optional) */}
          <div className="mt-8 space-y-3">
            <p className="text-sm text-gray-500 text-center">
              Want to add specific details? Type a note:
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddNote()}
                placeholder="Add a note (URLs, specific details, etc.)"
                className="flex-1 px-4 py-3 bg-white/50 backdrop-blur-sm border-2 border-gray-200 rounded-xl text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-msu-green-light transition-colors"
              />
              <button
                onClick={handleAddNote}
                disabled={!noteText.trim()}
                className="px-4 py-3 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed text-gray-700 rounded-xl transition-colors"
              >
                Add
              </button>
            </div>
          </div>

          {/* End interview button */}
          <div className="mt-8 text-center">
            <button
              onClick={handleComplete}
              className="text-sm text-gray-500 hover:text-gray-700 underline transition-colors"
            >
              End interview and generate profile
            </button>
          </div>
        </div>
      </div>

      {/* Footer status */}
      <div className="w-full pb-8 text-center">
        <p className="text-sm text-gray-500">
          {isConnected 
            ? 'Interview in progress - speak naturally, I\'m listening'
            : 'Connecting to voice service...'}
        </p>
      </div>
    </div>
  );
}
