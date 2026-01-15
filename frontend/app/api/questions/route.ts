import { NextResponse } from 'next/server';
import { getAllQuestions } from '@/lib/db';

export async function GET() {
  try {
    const questions = await getAllQuestions();
    return NextResponse.json({ questions });
  } catch (error) {
    console.error('Error fetching questions:', error);
    return NextResponse.json(
      { error: 'Failed to fetch questions' },
      { status: 500 }
    );
  }
}
