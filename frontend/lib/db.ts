import { Redis } from '@upstash/redis';
import { questions as defaultQuestions, Question } from './questions';

const QUESTIONS_KEY = 'msu-demo:questions:v2';

// Check if Redis is configured
const isRedisConfigured = !!(process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN);

// Only create Redis client if configured
const redis = isRedisConfigured ? Redis.fromEnv() : null;

export async function getAllQuestions(): Promise<Question[]> {
  // If Redis is not configured, use default questions (local development mode)
  if (!redis) {
    return defaultQuestions;
  }
  
  try {
    const questions = await redis.get<Question[]>(QUESTIONS_KEY);
    if (!questions) {
      // Initialize with default questions if none exist
      await redis.set(QUESTIONS_KEY, defaultQuestions);
      return defaultQuestions;
    }
    return questions;
  } catch (error) {
    console.warn('Redis error, falling back to default questions:', error);
    return defaultQuestions;
  }
}

export async function getQuestionById(id: string): Promise<Question | null> {
  const questions = await getAllQuestions();
  return questions.find(q => q.id === id) || null;
}

export async function saveAllQuestions(questions: Question[]): Promise<void> {
  if (!redis) {
    console.warn('Redis not configured - changes will not be persisted');
    return;
  }
  await redis.set(QUESTIONS_KEY, questions);
}

export async function createQuestion(question: Question): Promise<void> {
  if (!redis) {
    console.warn('Redis not configured - cannot create question');
    return;
  }
  const questions = await getAllQuestions();
  questions.push(question);
  await saveAllQuestions(questions);
}

export async function updateQuestion(id: string, updates: Partial<Question>): Promise<void> {
  if (!redis) {
    console.warn('Redis not configured - cannot update question');
    return;
  }
  const questions = await getAllQuestions();
  const index = questions.findIndex(q => q.id === id);
  if (index !== -1) {
    questions[index] = { ...questions[index], ...updates };
    await saveAllQuestions(questions);
  }
}

export async function deleteQuestion(id: string): Promise<void> {
  if (!redis) {
    console.warn('Redis not configured - cannot delete question');
    return;
  }
  const questions = await getAllQuestions();
  const filtered = questions.filter(q => q.id !== id);
  await saveAllQuestions(filtered);
}
