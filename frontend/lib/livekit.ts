/**
 * LiveKit connection utilities for voice interview
 */

import { Room, RoomEvent, ConnectionState, Track, Participant, RemoteTrack, RemoteTrackPublication } from 'livekit-client';

// Use local proxy to avoid mixed content issues (HTTPS -> HTTP)
// The proxy at /api/backend/* forwards to the actual backend
const API_BASE_URL = typeof window !== 'undefined' 
  ? ''  // Client-side: use local API routes
  : (process.env.BACKEND_API_URL || 'http://localhost:8000');  // Server-side: direct

export interface TokenResponse {
  token: string;
  url: string;
  room_name: string;
}

export interface VoiceQuestion {
  id: string;
  question: string;
  subtext?: string;
  conditional?: {
    dependsOn: string;
    values: string[];
  };
}

export interface VoiceQuestionsResponse {
  questions: VoiceQuestion[];
  phase: string;
  total_questions: number;
}

export interface AllQuestionsResponse {
  phases: string[];
  questions_by_phase: Record<string, VoiceQuestion[]>;
  total_questions: number;
}

/**
 * Get a LiveKit access token from the backend
 */
export async function getToken(
  roomName: string,
  participantName: string,
  interviewBriefing?: Record<string, unknown> | null,
  interviewPlan?: Record<string, unknown> | null,
): Promise<TokenResponse> {
  const body: Record<string, unknown> = {
    room_name: roomName,
    participant_name: participantName,
  };
  if (interviewBriefing) {
    body.interview_briefing = interviewBriefing;
  }
  if (interviewPlan) {
    body.interview_plan = interviewPlan;
  }

  const response = await fetch(`${API_BASE_URL}/api/backend/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Failed to get token: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get voice questions for a specific phase
 */
export async function getVoiceQuestions(phase: string, lifeStage?: string): Promise<VoiceQuestionsResponse> {
  const params = new URLSearchParams({ phase });
  if (lifeStage) {
    params.append('life_stage', lifeStage);
  }

  const response = await fetch(`${API_BASE_URL}/api/backend/voice-questions?${params}`);
  
  if (!response.ok) {
    throw new Error(`Failed to get questions: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get all voice questions organized by phase
 */
export async function getAllVoiceQuestions(lifeStage?: string): Promise<AllQuestionsResponse> {
  const params = new URLSearchParams();
  if (lifeStage) {
    params.append('life_stage', lifeStage);
  }

  const response = await fetch(`${API_BASE_URL}/api/backend/voice-questions/all?${params}`);
  
  if (!response.ok) {
    throw new Error(`Failed to get questions: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Extract profile from transcript
 */
export async function extractProfile(transcript: Array<{ role: string; text: string }>): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE_URL}/api/backend/extract-profile`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ transcript }),
  });

  if (!response.ok) {
    throw new Error(`Failed to extract profile: ${response.statusText}`);
  }

  const data = await response.json();
  return data.profile;
}

export type VoiceState = 'idle' | 'connecting' | 'listening' | 'thinking' | 'speaking' | 'error';

export interface VoiceSessionCallbacks {
  onStateChange?: (state: VoiceState) => void;
  onAgentTranscript?: (text: string, isFinal: boolean) => void;
  onUserTranscript?: (text: string, isFinal: boolean) => void;
  onError?: (error: Error) => void;
  onConnected?: () => void;
  onDisconnected?: () => void;
}

/**
 * Voice session manager for LiveKit connection
 */
export class VoiceSession {
  private room: Room | null = null;
  private callbacks: VoiceSessionCallbacks;
  private _state: VoiceState = 'idle';
  private transcript: Array<{ role: string; text: string; timestamp: string }> = [];

  constructor(callbacks: VoiceSessionCallbacks = {}) {
    this.callbacks = callbacks;
  }

  get state(): VoiceState {
    return this._state;
  }

  private setState(state: VoiceState) {
    this._state = state;
    this.callbacks.onStateChange?.(state);
  }

  getTranscript() {
    return [...this.transcript];
  }

  async connect(roomName: string, participantName: string): Promise<void> {
    try {
      this.setState('connecting');

      // Get token from backend
      const { token, url } = await getToken(roomName, participantName);

      // Create and connect room
      this.room = new Room({
        adaptiveStream: true,
        dynacast: true,
      });

      // Set up event listeners
      this.setupEventListeners();

      // Connect to room
      await this.room.connect(url, token);

      this.setState('listening');
      this.callbacks.onConnected?.();
    } catch (error) {
      this.setState('error');
      this.callbacks.onError?.(error as Error);
      throw error;
    }
  }

  private setupEventListeners() {
    if (!this.room) return;

    // Connection state changes
    this.room.on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
      if (state === ConnectionState.Disconnected) {
        this.setState('idle');
        this.callbacks.onDisconnected?.();
      }
    });

    // Track subscribed (agent audio)
    this.room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack, publication: RemoteTrackPublication, participant: Participant) => {
      if (track.kind === Track.Kind.Audio) {
        // Agent is speaking
        this.setState('speaking');
        
        // Attach audio to play
        const audioElement = track.attach();
        audioElement.play().catch(console.error);
      }
    });

    // Track unsubscribed
    this.room.on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
      if (track.kind === Track.Kind.Audio) {
        track.detach();
        this.setState('listening');
      }
    });

    // Data received (transcripts, state updates)
    this.room.on(RoomEvent.DataReceived, (payload: Uint8Array, participant?: Participant) => {
      try {
        const data = JSON.parse(new TextDecoder().decode(payload));
        
        if (data.type === 'transcript') {
          const { role, text, is_final } = data;
          
          if (role === 'agent') {
            this.callbacks.onAgentTranscript?.(text, is_final);
            if (is_final) {
              this.transcript.push({
                role: 'agent',
                text,
                timestamp: new Date().toISOString()
              });
            }
          } else if (role === 'user') {
            this.callbacks.onUserTranscript?.(text, is_final);
            if (is_final) {
              this.transcript.push({
                role: 'user',
                text,
                timestamp: new Date().toISOString()
              });
            }
          }
        } else if (data.type === 'state') {
          // Agent state updates
          if (data.state === 'thinking') {
            this.setState('thinking');
          } else if (data.state === 'speaking') {
            this.setState('speaking');
          } else if (data.state === 'listening') {
            this.setState('listening');
          }
        }
      } catch (e) {
        // Ignore non-JSON data
      }
    });
  }

  async enableMicrophone(): Promise<void> {
    if (!this.room) throw new Error('Not connected');
    
    await this.room.localParticipant.setMicrophoneEnabled(true);
  }

  async disableMicrophone(): Promise<void> {
    if (!this.room) throw new Error('Not connected');
    
    await this.room.localParticipant.setMicrophoneEnabled(false);
  }

  async toggleMicrophone(): Promise<boolean> {
    if (!this.room) throw new Error('Not connected');
    
    const isEnabled = this.room.localParticipant.isMicrophoneEnabled;
    await this.room.localParticipant.setMicrophoneEnabled(!isEnabled);
    return !isEnabled;
  }

  async disconnect(): Promise<void> {
    if (this.room) {
      await this.room.disconnect();
      this.room = null;
    }
    this.setState('idle');
  }

  isConnected(): boolean {
    return this.room?.state === ConnectionState.Connected;
  }
}

/**
 * Generate a unique room name for a voice interview session
 */
export function generateRoomName(userId?: string): string {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 8);
  const prefix = userId ? `user-${userId}` : 'interview';
  return `${prefix}-${timestamp}-${random}`;
}
