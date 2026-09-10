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
  usage: { llm_calls: number; prompt_tokens: number; completion_tokens: number; cost_usd: number };
  completion: { badges_awarded: string[]; completed_topics: number } | null;
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
