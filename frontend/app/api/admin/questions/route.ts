import { NextRequest, NextResponse } from 'next/server';
import { getAllQuestions, createQuestion, saveAllQuestions } from '@/lib/db';
import { questions as defaultQuestions } from '@/lib/questions';

// GET all questions
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

// POST create new question
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Get current max sort_order
    const questions = await getAllQuestions();
    const maxOrder = questions.length > 0
      ? Math.max(...questions.map((q: any) => q.sortOrder || 0))
      : 0;

    const newQuestion = {
      ...body,
      sortOrder: maxOrder + 1,
    };

    await createQuestion(newQuestion);

    return NextResponse.json({ success: true, question: newQuestion });
  } catch (error) {
    console.error('Error creating question:', error);
    return NextResponse.json(
      { error: 'Failed to create question' },
      { status: 500 }
    );
  }
}

// DELETE - Reset all questions to defaults
export async function DELETE() {
  try {
    await saveAllQuestions(defaultQuestions);
    return NextResponse.json({ success: true, message: 'Questions reset to defaults' });
  } catch (error) {
    console.error('Error resetting questions:', error);
    return NextResponse.json(
      { error: 'Failed to reset questions' },
      { status: 500 }
    );
  }
}
