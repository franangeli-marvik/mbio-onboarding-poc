import { generateText } from 'ai';
import { NextRequest, NextResponse } from 'next/server';
import { buildMbioPrompt } from '@/lib/mbio-engine';
import { GeneratedProfile } from '@/lib/types';

export async function POST(request: NextRequest) {
  try {
    const answers = await request.json();

    // Build the M.bio Engine prompt
    const prompt = buildMbioPrompt(answers);

    // Generate profile using Claude via Vercel AI Gateway
    const { text } = await generateText({
      model: 'anthropic/claude-3.7-sonnet',
      prompt,
      temperature: 0.7,
    });

    // Parse the JSON response
    let profile: GeneratedProfile;
    try {
      // Extract JSON from potential markdown code blocks
      const jsonMatch = text.match(/```(?:json)?\s*([\s\S]*?)\s*```/) || text.match(/(\{[\s\S]*\})/);
      const jsonString = jsonMatch ? jsonMatch[1] : text;
      profile = JSON.parse(jsonString.trim());
    } catch (parseError) {
      console.error('Failed to parse AI response:', text);
      throw new Error('Failed to parse profile JSON from AI response');
    }

    // Store in session or return directly
    return NextResponse.json({
      success: true,
      profile,
      answers, // Include original answers for reference
    });

  } catch (error) {
    console.error('Profile generation error:', error);
    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to generate profile'
      },
      { status: 500 }
    );
  }
}
