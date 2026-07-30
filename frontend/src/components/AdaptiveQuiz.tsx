import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { quizApi, type QuizQuestion, type EvaluationResult } from '@/lib/api';

interface AdaptiveQuizProps { topicId: string; topicTitle: string; onComplete: (newMastery: number) => void; gaps?: string[]; personaId?: string; }

const AdaptiveQuiz = ({ topicId, topicTitle, onComplete, gaps, personaId }: AdaptiveQuizProps) => {
  const { user } = useAuth();
  const [currentQuestion, setCurrentQuestion] = useState<QuizQuestion | null>(null);
  const [selectedAnswer, setSelectedAnswer] = useState('');
  const [mastery, setMastery] = useState(0.0);
  const [theta, setTheta] = useState(0.0);           // IRT ability estimate
  const [questionsAnswered, setQuestionsAnswered] = useState(0);
  const [loading, setLoading] = useState(true);
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null);
  const [showResult, setShowResult] = useState(false);

  useEffect(() => { fetchUserMastery(); }, [topicId, user]);

  const fetchUserMastery = async () => {
    if (!user) return;
    try {
      const { data } = await supabase
        .from('user_mastery')
        .select('mastery_level')
        .eq('user_id', user.id)
        .eq('topic_id', topicId)
        .single();
      const current = data?.mastery_level || 0;
      setMastery(current);
      generateQuestion(current);
    } catch {
      generateQuestion(0);
    }
  };

  const generateQuestion = async (masteryLevel: number) => {
    setLoading(true);
    try {
      const res = await quizApi.generateQuestion(topicTitle, masteryLevel, topicId, gaps, personaId);
      setCurrentQuestion(res.question);
      setTheta(res.theta);
    } catch (e: any) {
      toast.error(e.message || 'Failed to generate question');
    } finally {
      setLoading(false);
    }
  };

  const submitAnswer = async () => {
    if (!selectedAnswer || !currentQuestion || !user) { toast.error('Select an answer'); return; }
    setLoading(true);
    try {
      const res = await quizApi.evaluateAnswer({
        topic: topicTitle,
        topic_id: topicId,
        question: currentQuestion.question,
        answer: selectedAnswer,
        correct_answer: currentQuestion.correct_answer,
        mastery,
        theta,
      });
      setEvaluation(res.evaluation);
      setMastery(res.new_mastery);
      setTheta(res.new_theta);
      setShowResult(true);
      setQuestionsAnswered((p) => p + 1);
      if (res.evaluation.is_correct) toast.success(res.evaluation.feedback);
      else toast.error(res.evaluation.feedback);
    } catch (e: any) {
      toast.error(e.message || 'Failed to evaluate answer');
    } finally {
      setLoading(false);
    }
  };

  const nextQuestion = () => {
    if (questionsAnswered >= 5) { onComplete(mastery); return; }
    setSelectedAnswer(''); setEvaluation(null); setShowResult(false);
    generateQuestion(mastery);
  };

  const LEVEL_COLORS: Record<string, string> = {
    easy: 'text-green-600 dark:text-green-400',
    intermediate: 'text-yellow-600 dark:text-yellow-400',
    hard: 'text-red-600 dark:text-red-400',
  };

  if (loading && !currentQuestion) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-5 h-5 border-2 border-foreground border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Mastery + progress header */}
      <div className="card-base p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-0.5">Mastery</p>
            <p className="text-2xl font-bold text-foreground">{Math.round(mastery * 100)}%</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground mb-0.5">Question {Math.min(questionsAnswered + 1, 5)} of 5</p>
            <p className={`text-xs font-medium capitalize ${LEVEL_COLORS[currentQuestion?.difficulty ?? 'easy'] || ''}`}>
              {currentQuestion?.difficulty ?? 'loading'}
            </p>
          </div>
        </div>
        <div className="w-full h-1 bg-muted rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-foreground rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${mastery * 100}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          />
        </div>
        <div className="w-full h-1 bg-muted rounded-full overflow-hidden mt-1.5">
          <div className="h-full bg-muted-foreground/30 rounded-full" style={{ width: `${(questionsAnswered / 5) * 100}%` }} />
        </div>
        <div className="flex justify-between mt-1">
          <span className="text-[10px] text-muted-foreground">Mastery level</span>
          <span className="text-[10px] text-muted-foreground">Quiz progress</span>
        </div>
      </div>

      {/* Question */}
      {currentQuestion && (
        <motion.div key={questionsAnswered} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="card-base p-5">
          <p className="text-sm font-semibold text-foreground mb-4 leading-relaxed">{currentQuestion.question}</p>

          <RadioGroup value={selectedAnswer} onValueChange={setSelectedAnswer} className="space-y-2">
            {currentQuestion.options.map((option, i) => (
              <label
                key={i}
                htmlFor={`opt-${i}`}
                className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                  selectedAnswer === option
                    ? 'border-foreground bg-muted'
                    : 'border-border hover:border-muted-foreground hover:bg-muted/50'
                }`}
              >
                <RadioGroupItem value={option} id={`opt-${i}`} />
                <span className="text-sm text-foreground">{option}</span>
              </label>
            ))}
          </RadioGroup>

          {/* Result */}
          {evaluation && showResult && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={`mt-4 p-4 rounded-lg border text-sm ${
                evaluation.is_correct
                  ? 'border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/10 text-green-700 dark:text-green-400'
                  : 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/10 text-red-700 dark:text-red-400'
              }`}
            >
              <p className="font-semibold mb-1">Score: {Math.round(evaluation.score * 100)}%</p>
              <p className="text-xs opacity-80">{evaluation.feedback}</p>
              {evaluation.correction !== 'No correction needed.' && (
                <p className="text-xs mt-1 opacity-70"><strong>Correction:</strong> {evaluation.correction}</p>
              )}
            </motion.div>
          )}

          {/* Actions */}
          <div className="mt-4 flex gap-2">
            {!showResult ? (
              <Button
                onClick={submitAnswer}
                disabled={!selectedAnswer || loading}
                className="flex-1 h-9 bg-foreground text-background hover:bg-foreground/90 text-sm"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="w-3.5 h-3.5 border-2 border-background border-t-transparent rounded-full animate-spin" />
                    Evaluating...
                  </span>
                ) : 'Submit answer'}
              </Button>
            ) : (
              <Button
                onClick={nextQuestion}
                className="flex-1 h-9 bg-foreground text-background hover:bg-foreground/90 text-sm"
              >
                {questionsAnswered >= 5 ? 'Complete quiz' : 'Next question'}
              </Button>
            )}
          </div>
        </motion.div>
      )}
    </div>
  );
};

export default AdaptiveQuiz;
