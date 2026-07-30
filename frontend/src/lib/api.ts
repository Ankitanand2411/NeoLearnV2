import { supabase } from '@/integrations/supabase/client';

// FastAPI backend URL — change this when deployed
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

/**
 * Get the Supabase JWT and make an authenticated request to the FastAPI backend.
 */
async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;

  if (!token) throw new Error('Not authenticated');

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(options.headers ?? {}),
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }

  return res.json() as Promise<T>;
}

// ─── Quiz API ──────────────────────────────────────────────────────────────

export interface QuizQuestion {
  question: string;
  options: string[];
  correct_answer: string;
  difficulty: string;
  difficulty_param: number;
}

export interface GenerateQuestionResponse {
  success: boolean;
  question: QuizQuestion;
  theta: number;
}

export interface EvaluationResult {
  score: number;
  feedback: string;
  correction: string;
  is_correct: boolean;
}

export interface EvaluateAnswerResponse {
  success: boolean;
  evaluation: EvaluationResult;
  new_mastery: number;
  new_theta: number;
}

export const quizApi = {
  generateQuestion: (topic: string, mastery: number, topic_id?: string, gaps?: string[], persona_id?: string) =>
    apiRequest<GenerateQuestionResponse>('/quiz/generate', {
      method: 'POST',
      body: JSON.stringify({ topic, mastery, topic_id, gaps, persona_id }),
    }),

  evaluateAnswer: (params: {
    topic: string;
    topic_id: string;
    question: string;
    answer: string;
    correct_answer: string;
    mastery: number;
    theta: number;
  }) =>
    apiRequest<EvaluateAnswerResponse>('/quiz/evaluate', {
      method: 'POST',
      body: JSON.stringify(params),
    }),
};

// ─── Chat Evaluation API ───────────────────────────────────────────────────

export interface ChatEvaluateResponse {
  success: boolean;
  score: number;
  understood: string[];
  gaps: string[];
  reasoning: string;
}

export const chatApi = {
  evaluate: (params: {
    topic: string;
    topic_id: string;
    history: { role: string; content: string }[];
  }) =>
    apiRequest<ChatEvaluateResponse>('/chat/evaluate', {
      method: 'POST',
      body: JSON.stringify(params),
    }),
};


// ─── Analytics API ─────────────────────────────────────────────────────────

export interface LearningInsights {
  total_topics_attempted: number;
  avg_mastery: number;
  strongest_topic: string | null;
  weakest_topic: string | null;
  current_streak: number;
  longest_streak: number;
  total_questions: number;
  accuracy_rate: number;
  recommendation: string;
}

export const analyticsApi = {
  getInsights: () => apiRequest<LearningInsights>('/analytics/insights'),
};


// ─── Chat API (streaming SSE) ──────────────────────────────────────────────

export async function streamChat(
  message: string,
  topic: string,
  topic_id: string,
  mastery: number,
  history: { role: string; content: string }[],
  onToken: (token: string) => void,
  onDone: () => void,
  persona_id?: string
) {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) throw new Error('Not authenticated');

  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message, topic, topic_id, mastery, history, persona_id }),
  });

  if (!res.ok) throw new Error(`Chat error ${res.status}`);

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value);
    for (const line of text.split('\n')) {
      if (!line.startsWith('data: ')) continue;
      const payload = line.slice(6).trim();
      if (payload === '[DONE]') { onDone(); return; }
      try {
        const { token: t } = JSON.parse(payload);
        if (t) onToken(t);
      } catch { /* skip malformed chunks */ }
    }
  }
  onDone();
}
