'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

interface Question {
  id: string;
  phase: string;
  phaseLabel: string;
  question: string;
  subtext?: string;
  type: string;
  options?: { value: string; label: string }[];
  conditional?: {
    dependsOn: string;
    values: string[];
  };
  placeholder?: string;
}

export default function AdminPage() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<Question>>({});

  useEffect(() => {
    loadQuestions();
  }, []);

  const loadQuestions = async () => {
    try {
      const res = await fetch('/api/admin/questions');
      const data = await res.json();
      setQuestions(data.questions);
    } catch (error) {
      console.error('Failed to load questions:', error);
    } finally {
      setLoading(false);
    }
  };

  const startEdit = (question: Question) => {
    setEditingId(question.id);
    setEditForm(question);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditForm({});
  };

  const saveEdit = async () => {
    if (!editingId) return;

    try {
      await fetch(`/api/admin/questions/${editingId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm),
      });

      await loadQuestions();
      cancelEdit();
    } catch (error) {
      console.error('Failed to save question:', error);
      alert('Failed to save question');
    }
  };

  const deleteQuestion = async (id: string) => {
    if (!confirm('Are you sure you want to delete this question?')) return;

    try {
      await fetch(`/api/admin/questions/${id}`, {
        method: 'DELETE',
      });

      await loadQuestions();
    } catch (error) {
      console.error('Failed to delete question:', error);
      alert('Failed to delete question');
    }
  };

  const resetToDefaults = async () => {
    if (!confirm('This will reset ALL questions to their default values. Are you sure?')) return;

    try {
      await fetch('/api/admin/questions', {
        method: 'DELETE',
      });

      await loadQuestions();
      alert('Questions reset to defaults successfully!');
    } catch (error) {
      console.error('Failed to reset questions:', error);
      alert('Failed to reset questions');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-600">Loading...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Question Admin</h1>
            <p className="text-gray-600 mt-1">Manage questionnaire questions</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={resetToDefaults}
              className="px-4 py-2 bg-amber-100 text-amber-700 rounded-lg hover:bg-amber-200 transition-colors text-sm font-medium"
            >
              Reset to Defaults
            </button>
            <Link
              href="/"
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
            >
              ← Back to Home
            </Link>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Phase
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Question
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Type
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {questions.map((question) => (
                <tr key={question.id} className="hover:bg-gray-50">
                  {editingId === question.id ? (
                    <>
                      <td className="px-6 py-4 text-sm text-gray-500">{question.id}</td>
                      <td className="px-6 py-4">
                        <input
                          type="text"
                          value={editForm.phaseLabel || ''}
                          onChange={(e) => setEditForm({ ...editForm, phaseLabel: e.target.value })}
                          className="px-2 py-1 border rounded text-sm w-full"
                        />
                      </td>
                      <td className="px-6 py-4">
                        <textarea
                          value={editForm.question || ''}
                          onChange={(e) => setEditForm({ ...editForm, question: e.target.value })}
                          className="px-2 py-1 border rounded text-sm w-full"
                          rows={2}
                        />
                      </td>
                      <td className="px-6 py-4">
                        <select
                          value={editForm.type || ''}
                          onChange={(e) => setEditForm({ ...editForm, type: e.target.value })}
                          className="px-2 py-1 border rounded text-sm"
                        >
                          <option value="text">Text</option>
                          <option value="textarea">Textarea</option>
                          <option value="select">Select</option>
                        </select>
                      </td>
                      <td className="px-6 py-4 text-right space-x-2">
                        <button
                          onClick={saveEdit}
                          className="text-green-600 hover:text-green-900 text-sm font-medium"
                        >
                          Save
                        </button>
                        <button
                          onClick={cancelEdit}
                          className="text-gray-600 hover:text-gray-900 text-sm font-medium"
                        >
                          Cancel
                        </button>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="px-6 py-4 text-sm text-gray-500">{question.id}</td>
                      <td className="px-6 py-4 text-sm">
                        <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-medium">
                          {question.phaseLabel}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <p className="text-sm text-gray-900">{question.question}</p>
                        {question.subtext && (
                          <p className="text-xs text-gray-500 mt-1">{question.subtext}</p>
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">{question.type}</td>
                      <td className="px-6 py-4 text-right space-x-2">
                        <button
                          onClick={() => startEdit(question)}
                          className="text-blue-600 hover:text-blue-900 text-sm font-medium"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => deleteQuestion(question.id)}
                          className="text-red-600 hover:text-red-900 text-sm font-medium"
                        >
                          Delete
                        </button>
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="text-sm text-gray-500 mt-4">
          {questions.length} questions total
        </p>
      </div>
    </div>
  );
}
