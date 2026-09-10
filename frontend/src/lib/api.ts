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
    difficulty_param?: number; // IRT b of the question being answered
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


// ─── Session API (server-side LangGraph session) ───────────────────────────
// The tutor → judge → quiz state machine now runs on the server. The client
// never sees an unanswered question's correct answer; grading happens against
// the server-held key and the answer is revealed only in `evaluation`.

export interface PublicQuestion {
  index: number;
  question: string;
  options: string[];
  difficulty: string;
  difficulty_param: number;
}

export interface GradedAnswer {
  index: number;
  answer: string;
  is_correct: boolean;
  score: number;
  feedback: string;
  correction: string;
  correct_answer: string;
}

export interface SessionVerdict {
  score: number;
  understood: string[];
  gaps: string[];
  reasoning: string;
}

export interface SessionView {
  session_id: string;
  phase: 'tutor' | 'quiz' | 'done';
  pending_step: string | null;
  completed: boolean;
  mastery: number;
  theta: number;
  theta_sd: number | null;
  student_turns: number;
  can_evaluate: boolean;
  messages: { role: string; content: string }[];
  verdict: SessionVerdict | null;
  question: PublicQuestion | null;
  quiz: { index: number; total: number; answers: GradedAnswer[] };
  evaluation?: GradedAnswer | null;
}

export interface MessageDone {
  student_turns: number;
  can_evaluate: boolean;
}

export const sessionApi = {
  start: (params: { topic_id: string; topic: string; persona_id?: string | null; mastery?: number }) =>
    apiRequest<SessionView>('/session/start', { method: 'POST', body: JSON.stringify(params) }),

  get: (sessionId: string) => apiRequest<SessionView>(`/session/${sessionId}`),

  evaluate: (sessionId: string) =>
    apiRequest<SessionView>(`/session/${sessionId}/evaluate`, { method: 'POST' }),

  answer: (sessionId: string, answer: string) =>
    apiRequest<SessionView>(`/session/${sessionId}/answer`, {
      method: 'POST',
      body: JSON.stringify({ answer }),
    }),

  continue: (sessionId: string) =>
    apiRequest<SessionView>(`/session/${sessionId}/continue`, { method: 'POST' }),

  /** One tutor turn, streamed. Resolves with the `done` metadata once the stream ends. */
  streamMessage: async (
    sessionId: string,
    message: string,
    onToken: (token: string) => void,
  ): Promise<MessageDone> => {
    const { data: { session } } = await supabase.auth.getSession();
    const token = session?.access_token;
    if (!token) throw new Error('Not authenticated');

    const res = await fetch(`${API_BASE}/session/${sessionId}/message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ message }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Chat error ${res.status}`);
    }

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let done: MessageDone | null = null;

    while (true) {
      const { done: finished, value } = await reader.read();
      if (finished) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';            // keep a partial trailing line for the next chunk
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const payload = line.slice(6).trim();
        if (payload === '[DONE]') break;
        try {
          const obj = JSON.parse(payload);
          if (obj.token) onToken(obj.token);
          else if (obj.done) done = { student_turns: obj.student_turns, can_evaluate: obj.can_evaluate };
          else if (obj.error) throw new Error(obj.error);
        } catch (e) {
          if (e instanceof Error && e.message && !e.message.startsWith('Unexpected')) throw e;
        }
      }
    }
    if (!done) throw new Error('The tutor stream ended unexpectedly');
    return done;
  },
};
