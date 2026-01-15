'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { VoiceSession, VoiceState, generateRoomName } from '@/lib/livekit';

export interface UseVoiceSessionOptions {
  participantName: string;
  onAgentTranscript?: (text: string, isFinal: boolean) => void;
  onUserTranscript?: (text: string, isFinal: boolean) => void;
  onError?: (error: Error) => void;
}

export interface UseVoiceSessionReturn {
  state: VoiceState;
  isConnected: boolean;
  isMicEnabled: boolean;
  agentText: string;
  userText: string;
  transcript: Array<{ role: string; text: string; timestamp: string }>;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  toggleMic: () => Promise<void>;
  enableMic: () => Promise<void>;
  disableMic: () => Promise<void>;
}

export function useVoiceSession(options: UseVoiceSessionOptions): UseVoiceSessionReturn {
  const { participantName, onAgentTranscript, onUserTranscript, onError } = options;
  
  const [state, setState] = useState<VoiceState>('idle');
  const [isConnected, setIsConnected] = useState(false);
  const [isMicEnabled, setIsMicEnabled] = useState(false);
  const [agentText, setAgentText] = useState('');
  const [userText, setUserText] = useState('');
  const [transcript, setTranscript] = useState<Array<{ role: string; text: string; timestamp: string }>>([]);
  
  const sessionRef = useRef<VoiceSession | null>(null);
  const roomNameRef = useRef<string>('');

  // Initialize session
  useEffect(() => {
    sessionRef.current = new VoiceSession({
      onStateChange: (newState) => {
        setState(newState);
      },
      onAgentTranscript: (text, isFinal) => {
        setAgentText(text);
        onAgentTranscript?.(text, isFinal);
        if (isFinal) {
          setTranscript(prev => [...prev, {
            role: 'agent',
            text,
            timestamp: new Date().toISOString()
          }]);
        }
      },
      onUserTranscript: (text, isFinal) => {
        setUserText(text);
        onUserTranscript?.(text, isFinal);
        if (isFinal) {
          setTranscript(prev => [...prev, {
            role: 'user',
            text,
            timestamp: new Date().toISOString()
          }]);
          setUserText(''); // Clear after final
        }
      },
      onError: (error) => {
        onError?.(error);
      },
      onConnected: () => {
        setIsConnected(true);
      },
      onDisconnected: () => {
        setIsConnected(false);
        setIsMicEnabled(false);
      },
    });

    return () => {
      sessionRef.current?.disconnect();
    };
  }, [onAgentTranscript, onUserTranscript, onError]);

  const connect = useCallback(async () => {
    if (!sessionRef.current) return;
    
    roomNameRef.current = generateRoomName();
    await sessionRef.current.connect(roomNameRef.current, participantName);
  }, [participantName]);

  const disconnect = useCallback(async () => {
    if (!sessionRef.current) return;
    await sessionRef.current.disconnect();
  }, []);

  const toggleMic = useCallback(async () => {
    if (!sessionRef.current) return;
    const enabled = await sessionRef.current.toggleMicrophone();
    setIsMicEnabled(enabled);
  }, []);

  const enableMic = useCallback(async () => {
    if (!sessionRef.current) return;
    await sessionRef.current.enableMicrophone();
    setIsMicEnabled(true);
  }, []);

  const disableMic = useCallback(async () => {
    if (!sessionRef.current) return;
    await sessionRef.current.disableMicrophone();
    setIsMicEnabled(false);
  }, []);

  return {
    state,
    isConnected,
    isMicEnabled,
    agentText,
    userText,
    transcript,
    connect,
    disconnect,
    toggleMic,
    enableMic,
    disableMic,
  };
}
