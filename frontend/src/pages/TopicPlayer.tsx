import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/contexts/AuthContext';
import Navbar from '@/components/Navbar';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft,
  MessageSquare,
  Award,
  Sparkles,
  BookOpen,
  Send,
  HelpCircle,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Zap,
} from 'lucide-react';
import { toast } from 'sonner';
import type { Topic } from '@/types/Topic';
import AdaptiveQuiz from '@/components/AdaptiveQuiz';
import ThemeToggle from '@/components/ThemeToggle';
import { streamChat, chatApi } from '@/lib/api';

const STEPS = [
  { label: 'Socratic Dialogue', icon: MessageSquare },
  { label: 'AI Evaluation', icon: Award },
  { label: 'Targeted Remediation', icon: Sparkles },
];

interface ChatMsg {
  role: 'user' | 'assistant';
  content: string;
}

const PERSONAS: Record<string, { name: string; domain: string; initial: string; color: string; avatar?: string }> = {
  einstein:    { name: 'Albert Einstein',       domain: 'Physics & Relativity',          initial: 'AE', color: 'bg-blue-600', avatar: 'https://upload.wikimedia.org/wikipedia/commons/3/3e/Einstein_1921_by_F_Schmutzer_-_restoration.jpg' },
  feynman:     { name: 'Richard Feynman',       domain: 'Quantum Mechanics',             initial: 'RF', color: 'bg-violet-600', avatar: 'https://upload.wikimedia.org/wikipedia/en/4/42/Richard_Feynman_Nobel.jpg' },
  curie:       { name: 'Marie Curie',           domain: 'Chemistry',                     initial: 'MC', color: 'bg-teal-600', avatar: 'https://upload.wikimedia.org/wikipedia/commons/c/c8/Marie_Curie_c._1920s.jpg' },
  socrates:    { name: 'Socrates',              domain: 'Philosophy',                    initial: 'S',  color: 'bg-amber-600', avatar: 'https://upload.wikimedia.org/wikipedia/commons/a/a4/Socrates_Louvre.jpg' },
  turing:      { name: 'Alan Turing',           domain: 'Computer Science',              initial: 'AT', color: 'bg-emerald-600', avatar: 'https://upload.wikimedia.org/wikipedia/commons/a/a1/Alan_Turing_Aged_16.jpg' },
  darwin:      { name: 'Charles Darwin',        domain: 'Biology & Evolution',           initial: 'CD', color: 'bg-lime-700', avatar: 'https://upload.wikimedia.org/wikipedia/commons/2/2e/Charles_Darwin_seated_crop.jpg' },
  nightingale: { name: 'Florence Nightingale',  domain: 'Statistics',                   initial: 'FN', color: 'bg-rose-600', avatar: 'https://upload.wikimedia.org/wikipedia/commons/1/17/Florence_Nightingale.cdv.jpg' },
  gandhi:      { name: 'Mahatma Gandhi',        domain: 'Leadership & Ethics',           initial: 'MG', color: 'bg-orange-600', avatar: 'https://upload.wikimedia.org/wikipedia/commons/7/7a/Mahatma-Gandhi%2C_studio%2C_1931.jpg' },
  ramanujan:   { name: 'Srinivasa Ramanujan',   domain: 'Mathematics',                  initial: 'SR', color: 'bg-indigo-600', avatar: 'https://upload.wikimedia.org/wikipedia/commons/c/c1/Srinivasa_Ramanujan_-_OPC_-_1.jpg' },
  twain:       { name: 'Mark Twain',            domain: 'Literature & Writing',         initial: 'MT', color: 'bg-yellow-700', avatar: 'https://upload.wikimedia.org/wikipedia/commons/0/0c/Mark_Twain_by_AF_Bradley.jpg' },
};

const TopicPlayer = () => {
  const { topicId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  
  const [topic, setTopic] = useState<Topic | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [userMasteryLevel, setUserMasteryLevel] = useState(0);
  const [loading, setLoading] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(220);

  // Chat State
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [inputMsg, setInputMsg] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Evaluation / Judge State
  const [evaluating, setEvaluating] = useState(false);
  const [evalResult, setEvalResult] = useState<{
    score: number;
    understood: string[];
    gaps: string[];
    reasoning: string;
  } | null>(null);

  useEffect(() => {
    const fetchTopic = async () => {
      if (!topicId || !user) return;
      try {
        const { data: topicData, error } = await supabase
          .from('topics')
          .select('*')
          .eq('id', topicId)
          .single();
        if (error) throw error;
        
        const { data: masteryData } = await supabase
          .from('user_mastery')
          .select('mastery_level')
          .eq('user_id', user.id)
          .eq('topic_id', topicId)
          .single();
          
        if (topicData) {
          setTopic({ ...topicData, estimated_time: 30 });
          setUserMasteryLevel(masteryData?.mastery_level || 0);

          const mentorName = PERSONAS[topicData.mentor_id || '']?.name || 'Your Mentor';
          
          // Seed initial Tutor message
          setMessages([
            {
              role: 'assistant',
              content: `Greetings! I am ${mentorName}. Let us explore "${topicData.title}" together. In your own words, tell me what you currently understand about this topic. Do not be afraid to be incomplete — we shall build understanding step by step.`,
            },
          ]);
        } else {
          toast.error('Topic not found');
          navigate('/learn');
        }
      } catch (err) {
        toast.error('Failed to load topic');
        navigate('/learn');
      } finally {
        setLoading(false);
      }
    };
    fetchTopic();
  }, [topicId, user, navigate]);

  // Scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const handleSendMessage = async () => {
    if (!inputMsg.trim() || isTyping || !topic) return;
    const userMsgText = inputMsg.trim();
    setInputMsg('');
    
    // Add User message
    const updatedHistory = [...messages, { role: 'user', content: userMsgText } as ChatMsg];
    setMessages(updatedHistory);
    setIsTyping(true);

    // Prepare container for tutor's stream
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);

    try {
      let accumulatedToken = '';
      await streamChat(
        userMsgText,
        topic.title,
        topic.id,
        userMasteryLevel,
        // Send history without the last placeholder empty assistant response
        updatedHistory,
        (token) => {
          accumulatedToken += token;
          setMessages((prev) => {
            const next = [...prev];
            if (next.length > 0) {
              next[next.length - 1] = {
                role: 'assistant',
                content: accumulatedToken,
              };
            }
            return next;
          });
        },
        () => {
          setIsTyping(false);
        },
        topic.mentor_id
      );
    } catch (err: any) {
      toast.error('Failed to get response from Socratic Tutor.');
      setIsTyping(false);
    }
  };

  const handleRunEvaluation = async () => {
    if (!topic || messages.length < 3 || evaluating) return;
    setEvaluating(true);
    setCurrentStep(1); // Move to Evaluation step
    
    try {
      const res = await chatApi.evaluate({
        topic: topic.title,
        topic_id: topic.id,
        history: messages,
      });
      if (res.success) {
        setEvalResult({
          score: res.score,
          understood: res.understood,
          gaps: res.gaps,
          reasoning: res.reasoning,
        });
        setUserMasteryLevel(res.score);
        toast.success('AI evaluation completed successfully!');
      } else {
        throw new Error('Evaluation field missing success flag');
      }
    } catch (err: any) {
      toast.error(err.message || 'Evaluation failed. Please try again.');
      setCurrentStep(0); // bounce back to chat
    } finally {
      setEvaluating(false);
    }
  };

  const handleQuizComplete = async (newMastery: number) => {
    if (!user || !topic) return;
    try {
      const { error: progressError } = await supabase
        .from('user_progress')
        .insert({ user_id: user.id, topic_id: topic.id });
      if (progressError && !progressError.message.includes('duplicate')) throw progressError;

      const { data: existingProgress } = await supabase
        .from('user_progress')
        .select('id')
        .eq('user_id', user.id);
        
      if (existingProgress && existingProgress.length === 1) {
        await supabase.from('user_badges').insert({ user_id: user.id, badge_name: 'First Steps' });
        toast.success('Badge earned: First Steps');
      }
      
      if (newMastery >= 0.9) {
        await supabase.from('user_badges').insert({ user_id: user.id, badge_name: 'Master' });
        toast.success('Badge earned: Master');
      } else if (newMastery >= 0.7) {
        await supabase.from('user_badges').insert({ user_id: user.id, badge_name: 'Expert' });
        toast.success('Badge earned: Expert');
      }
      
      setUserMasteryLevel(newMastery);
      toast.success(`Topic complete — Mastery: ${Math.round(newMastery * 100)}%`);
      setTimeout(() => navigate('/learn'), 2500);
    } catch {
      toast.error('Something went wrong saving your final progress.');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <Navbar onSidebarWidthChange={setSidebarWidth} />
        <div
          className="flex items-center justify-center min-h-screen"
          style={{ marginLeft: sidebarWidth, width: `calc(100% - ${sidebarWidth}px)` }}
        >
          <div className="w-5 h-5 border-2 border-foreground border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (!topic) {
    return (
      <div className="min-h-screen bg-background">
        <Navbar onSidebarWidthChange={setSidebarWidth} />
        <div
          className="flex items-center justify-center min-h-screen"
          style={{ marginLeft: sidebarWidth, width: `calc(100% - ${sidebarWidth}px)` }}
        >
          <div className="card-base p-8 text-center">
            <h2 className="text-lg font-semibold text-foreground mb-3">Topic not found</h2>
            <Button
              onClick={() => navigate('/learn')}
              size="sm"
              className="bg-foreground text-background hover:bg-foreground/90"
            >
              Back to topics
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const progress = ((currentStep + 1) / STEPS.length) * 100;
  const userRepliesCount = messages.filter((m) => m.role === 'user').length;
  const canEvaluate = userRepliesCount >= 3;

  return (
    <div className="min-h-screen bg-background text-foreground transition-colors duration-300">
      <Navbar onSidebarWidthChange={setSidebarWidth} />
      <div className="fixed top-4 right-5 z-40">
        <ThemeToggle />
      </div>

      <main
        className="px-6 py-8 flex flex-col min-h-screen"
        style={{
          marginLeft: sidebarWidth,
          width: `calc(100% - ${sidebarWidth}px)`,
          transition: 'margin-left 0.25s, width 0.25s',
        }}
      >
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mb-6">
          <button
            onClick={() => navigate('/learn')}
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors mb-4"
          >
            <ArrowLeft size={14} /> Back to topics
          </button>
          
          <div className="card-base p-5 bg-gradient-to-br from-card to-muted/40 border border-border/80 shadow-md">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-1">
                  {topic.difficulty} • Socratic Mode
                </p>
                <h1 className="text-2xl font-extrabold tracking-tight text-foreground">{topic.title}</h1>
                <p className="text-sm text-muted-foreground mt-1 leading-relaxed">{topic.description}</p>
              </div>
              <div className="shrink-0 text-right bg-background/50 px-4 py-2 rounded-lg border border-border/60">
                <p className="text-xs text-muted-foreground font-medium">Topic Mastery</p>
                <p className="text-2xl font-black text-foreground">
                  {Math.round(userMasteryLevel * 100)}%
                </p>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Step Indicator */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="card-base p-4 mb-6 border border-border/60 shadow-sm"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-6">
              {STEPS.map((step, i) => {
                const Icon = step.icon;
                const isActive = i === currentStep;
                const isCompleted = i < currentStep;
                return (
                  <div
                    key={step.label}
                    className={`flex items-center gap-2 text-xs font-semibold ${
                      isActive
                        ? 'text-foreground'
                        : isCompleted
                        ? 'text-green-500'
                        : 'text-muted-foreground/40'
                    }`}
                  >
                    <div
                      className={`p-1.5 rounded-md ${
                        isActive
                          ? 'bg-foreground text-background'
                          : isCompleted
                          ? 'bg-green-500/10 text-green-500'
                          : 'bg-muted text-muted-foreground/30'
                      }`}
                    >
                      <Icon size={13} />
                    </div>
                    {step.label}
                  </div>
                );
              })}
            </div>
            <span className="text-xs font-medium text-muted-foreground">
              Step {currentStep + 1} of {STEPS.length}
            </span>
          </div>
          <div className="w-full h-1 bg-muted rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-foreground rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.4, ease: 'easeOut' }}
            />
          </div>
        </motion.div>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-h-0">
          <AnimatePresence mode="wait">
            {currentStep === 0 && (
              <motion.div
                key="step-chat"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="flex-1 flex justify-center h-full"
              >
                {/* Socratic Chat Panel (Centered) */}
                <div className="w-full max-w-5xl flex flex-col card-base p-0 overflow-hidden border border-border/80 bg-card/40 backdrop-blur-md shadow-md flex-1">
                  {/* Chat Header */}
                  <div className="px-5 py-4 border-b border-border/60 bg-muted/20 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="relative">
                        <div className="w-10 h-10 rounded-full bg-muted overflow-hidden border border-border/80 shadow-sm shrink-0">
                          {topic.mentor_id && PERSONAS[topic.mentor_id]?.avatar ? (
                            <img src={PERSONAS[topic.mentor_id].avatar} alt={PERSONAS[topic.mentor_id].name} className="w-full h-full object-cover" />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center bg-foreground text-background font-bold text-xs">
                              {PERSONAS[topic.mentor_id || '']?.initial || 'AI'}
                            </div>
                          )}
                        </div>
                        <div className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-green-500 border-2 border-background" />
                      </div>
                      <div>
                        <p className="text-sm font-bold text-foreground">
                          {PERSONAS[topic.mentor_id || '']?.name || 'Socratic Mentor'}
                        </p>
                        <p className="text-[10px] text-muted-foreground">Historical Mentor · RAG Grounded Socratic Chain</p>
                      </div>
                    </div>
                    <div className="text-xs font-semibold text-muted-foreground bg-muted px-3 py-1.5 rounded-full">
                      Dialogue Depth: {userRepliesCount} / 3 replies
                    </div>
                  </div>

                  {/* Messages Feed */}
                  <div className="flex-1 overflow-y-auto p-5 space-y-4">
                    {messages.map((msg, i) => (
                      <div
                        key={i}
                        className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                      >
                        <div
                          className={`max-w-[85%] rounded-2xl p-4 text-[13px] leading-relaxed shadow-sm transition-all ${
                            msg.role === 'user'
                              ? 'bg-foreground text-background font-medium rounded-tr-none'
                              : 'bg-muted/80 text-foreground border border-border/50 rounded-tl-none'
                          }`}
                        >
                          {msg.content === '' && isTyping ? (
                            <span className="flex gap-1 items-center justify-center py-1">
                              <span className="w-1.5 h-1.5 bg-foreground/60 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                              <span className="w-1.5 h-1.5 bg-foreground/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                              <span className="w-1.5 h-1.5 bg-foreground/60 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                            </span>
                          ) : (
                            msg.content
                          )}
                        </div>
                      </div>
                    ))}
                    <div ref={chatEndRef} />
                  </div>

                  {/* Input bar */}
                  <div className="p-4 border-t border-border/60 bg-muted/10 space-y-3">
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={inputMsg}
                        onChange={(e) => setInputMsg(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSendMessage();
                        }}
                        disabled={isTyping}
                        placeholder={
                          isTyping
                            ? 'Tutor is thinking...'
                            : 'Type your explanation or query here...'
                        }
                        className="flex-1 bg-background text-sm text-foreground rounded-lg border border-border/80 px-3.5 py-2 focus:outline-none focus:border-foreground/40 transition-colors"
                      />
                      <Button
                        onClick={handleSendMessage}
                        disabled={isTyping || !inputMsg.trim()}
                        size="icon"
                        className="bg-foreground text-background hover:bg-foreground/90 transition-all shadow-md shrink-0 w-9 h-9"
                      >
                        <Send size={15} />
                      </Button>
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-[10px] text-muted-foreground/75">
                        {!canEvaluate
                          ? `Provide at least ${3 - userRepliesCount} more explanations to unlock evaluation`
                          : 'You have unlocked the AI Mastery Evaluation!'}
                      </span>
                      {canEvaluate && (
                        <Button
                          onClick={handleRunEvaluation}
                          size="sm"
                          className="h-8 px-4 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white text-[11px] font-bold tracking-wide uppercase transition-all shadow-sm"
                        >
                          Evaluate Understanding <Award size={13} className="ml-1.5" />
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {currentStep === 1 && (
              <motion.div
                key="step-eval"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="flex-grow flex flex-col justify-center max-w-3xl mx-auto w-full"
              >
                {evaluating || !evalResult ? (
                  <div className="card-base p-12 text-center flex flex-col items-center justify-center space-y-4">
                    <RefreshCw className="w-8 h-8 text-foreground animate-spin" />
                    <h3 className="text-base font-bold text-foreground">AI Judge is evaluating...</h3>
                    <p className="text-xs text-muted-foreground max-w-sm">
                      Analyzing conversation history, extracting knowledge retention metrics, and diagnosing conceptual gaps. This takes a few seconds.
                    </p>
                  </div>
                ) : (
                  <motion.div
                    initial={{ scale: 0.98 }}
                    animate={{ scale: 1 }}
                    className="card-base p-6 md:p-8 space-y-6 border border-border/80 bg-card/60 backdrop-blur-md shadow-lg"
                  >
                    <div className="text-center pb-4 border-b border-border/60">
                      <h2 className="text-lg font-extrabold text-foreground tracking-tight flex items-center justify-center gap-2">
                        <Award className="text-indigo-500" size={18} /> Socratic AI Evaluation Report
                      </h2>
                      <p className="text-xs text-muted-foreground mt-1">
                        Topic: {topic.title}
                      </p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
                      {/* Gauge */}
                      <div className="flex flex-col items-center justify-center bg-background/40 p-5 rounded-2xl border border-border/50">
                        <div className="relative w-24 h-24 flex items-center justify-center">
                          <svg className="w-full h-full transform -rotate-90">
                            <circle
                              cx="48"
                              cy="48"
                              r="38"
                              className="stroke-muted"
                              strokeWidth="6"
                              fill="transparent"
                            />
                            <motion.circle
                              cx="48"
                              cy="48"
                              r="38"
                              className="stroke-foreground"
                              strokeWidth="6"
                              fill="transparent"
                              strokeDasharray="238"
                              initial={{ strokeDashoffset: 238 }}
                              animate={{ strokeDashoffset: 238 - (238 * evalResult.score) }}
                              transition={{ duration: 1.2, ease: 'easeOut' }}
                            />
                          </svg>
                          <span className="absolute text-xl font-black text-foreground">
                            {Math.round(evalResult.score * 100)}%
                          </span>
                        </div>
                        <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-widest mt-3">
                          Mastery Score
                        </p>
                      </div>

                      {/* Detail report */}
                      <div className="md:col-span-2 space-y-4">
                        <div>
                          <h3 className="text-xs font-extrabold uppercase tracking-wide text-muted-foreground mb-1.5 flex items-center gap-1.5">
                            <CheckCircle className="text-green-500" size={13} /> Understood Concepts
                          </h3>
                          <div className="flex flex-wrap gap-1.5">
                            {evalResult.understood.length > 0 ? (
                              evalResult.understood.map((item, idx) => (
                                <span
                                  key={idx}
                                  className="text-[10px] font-semibold bg-green-500/10 text-green-600 dark:text-green-400 px-2.5 py-1 rounded-full border border-green-500/20"
                                >
                                  {item}
                                </span>
                              ))
                            ) : (
                              <span className="text-xs text-muted-foreground italic">None identified</span>
                            )}
                          </div>
                        </div>

                        <div>
                          <h3 className="text-xs font-extrabold uppercase tracking-wide text-muted-foreground mb-1.5 flex items-center gap-1.5">
                            <AlertTriangle className="text-amber-500" size={13} /> Identified Gaps
                          </h3>
                          <div className="flex flex-wrap gap-1.5">
                            {evalResult.gaps.length > 0 ? (
                              evalResult.gaps.map((item, idx) => (
                                <span
                                  key={idx}
                                  className="text-[10px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 px-2.5 py-1 rounded-full border border-amber-500/20"
                                >
                                  {item}
                                </span>
                              ))
                            ) : (
                              <span className="text-[10px] font-semibold bg-green-500/10 text-green-600 dark:text-green-400 px-2.5 py-1 rounded-full border border-green-500/20">
                                Perfect! No conceptual gaps detected.
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="bg-muted/40 p-4 rounded-xl border border-border/50 text-xs text-muted-foreground leading-relaxed">
                      <p className="font-bold text-foreground mb-1.5">AI Judge Commentary:</p>
                      {evalResult.reasoning}
                    </div>

                    <div className="flex justify-end gap-3 pt-3 border-t border-border/60">
                      <Button
                        variant="outline"
                        onClick={() => {
                          // Allow re-explaining to improve
                          setCurrentStep(0);
                        }}
                        className="h-9 px-4 text-xs font-semibold"
                      >
                        Re-discuss with Tutor
                      </Button>
                      <Button
                        onClick={() => setCurrentStep(2)}
                        className="h-9 px-5 bg-foreground text-background hover:bg-foreground/90 text-xs font-bold transition-all shadow-md"
                      >
                        Proceed to Targeted Quiz <ArrowLeft className="rotate-180 ml-1.5" size={13} />
                      </Button>
                    </div>
                  </motion.div>
                )}
              </motion.div>
            )}

            {currentStep === 2 && (
              <motion.div
                key="step-quiz"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="max-w-2xl mx-auto w-full"
              >
                <AdaptiveQuiz
                  topicId={topic.id}
                  topicTitle={topic.title}
                  onComplete={handleQuizComplete}
                  gaps={evalResult?.gaps || []}
                  personaId={topic.mentor_id}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
};

export default TopicPlayer;
