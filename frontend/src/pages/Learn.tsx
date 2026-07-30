import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/contexts/AuthContext';
import Navbar from '@/components/Navbar';
import { CheckCircle2, TrendingUp, ArrowRight, BookOpen } from 'lucide-react';
import { toast } from 'sonner';
import { motion } from 'framer-motion';

interface Topic {
  id: string;
  title: string;
  description: string;
  difficulty: string;
  mentor_id: string;
  estimated_time?: number;
}

interface UserMastery { topic_id: string; mastery_level: number; }

// ─── Persona metadata (mirrors persona_registry.py) ──────────────────────────
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

const getDifficultyColor = (difficulty: string) => {
  const d = difficulty?.toLowerCase();
  if (d === 'beginner') return 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20';
  if (d === 'intermediate') return 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20';
  if (d === 'advanced') return 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/20';
  return 'bg-muted text-muted-foreground border-border';
};

const getMasteryLabel = (level: number) => {
  if (level === 0) return 'Not started';
  if (level < 0.3) return 'Beginner';
  if (level < 0.7) return 'Intermediate';
  return 'Advanced';
};

const Learn = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [topics, setTopics] = useState<Topic[]>([]);
  const [completedTopics, setCompletedTopics] = useState<string[]>([]);
  const [userMastery, setUserMastery] = useState<UserMastery[]>([]);
  const [loading, setLoading] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(220);

  useEffect(() => {
    const fetchTopics = async () => {
      if (!user) return;
      try {
        const { data: topicsData } = await supabase
          .from('topics')
          .select('*')
          .order('difficulty');
        const { data: progressData } = await supabase
          .from('user_progress')
          .select('topic_id')
          .eq('user_id', user.id);
        const { data: masteryData } = await supabase
          .from('user_mastery')
          .select('topic_id, mastery_level')
          .eq('user_id', user.id);
        setTopics(topicsData?.map((t) => ({ ...t, estimated_time: 30 })) || []);
        setCompletedTopics(progressData?.map((p) => p.topic_id) || []);
        setUserMastery(masteryData || []);
      } catch {
        toast.error('Failed to load topics');
      } finally {
        setLoading(false);
      }
    };
    fetchTopics();
  }, [user]);

  const getMastery = (topicId: string) =>
    userMastery.find((m) => m.topic_id === topicId)?.mastery_level || 0;

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <Navbar onSidebarWidthChange={setSidebarWidth} />
        <div className="flex items-center justify-center min-h-screen" style={{ marginLeft: sidebarWidth, width: `calc(100% - ${sidebarWidth}px)` }}>
          <div className="spinner" />
        </div>
      </div>
    );
  }

  const completedCount = completedTopics.length;
  const progress = topics.length > 0 ? Math.round((completedCount / topics.length) * 100) : 0;

  return (
    <div className="min-h-screen bg-background">
      <Navbar onSidebarWidthChange={setSidebarWidth} />

      <main
        className="px-8 py-8"
        style={{ marginLeft: sidebarWidth, width: `calc(100% - ${sidebarWidth}px)`, transition: 'margin-left 0.25s, width 0.25s' }}
      >
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="mb-10">
          <p className="section-label mb-2">Learning</p>
          <h1 className="heading-display mb-2">Choose Your Mentor</h1>
          <p className="text-muted-foreground text-sm">
            Each topic is taught by a historical expert — using the Socratic method, grounded in their documented thinking style.
          </p>
        </motion.div>

        {/* Progress card */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.06 }}
          className="card-base p-6 mb-8"
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="section-label mb-1">Your progress</p>
              <p className="text-sm text-muted-foreground">{completedCount} of {topics.length} mentor sessions completed</p>
            </div>
            <span className="text-4xl font-bold text-foreground tracking-tight">{progress}%</span>
          </div>
          <div className="progress-track">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ delay: 0.4, duration: 0.9, ease: 'easeOut' }}
              className="progress-fill"
            />
          </div>
        </motion.div>

        {/* Topics */}
        {topics.length === 0 ? (
          <div className="card-base p-14 text-center">
            <div className="w-12 h-12 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
              <BookOpen size={20} className="text-muted-foreground" />
            </div>
            <h3 className="text-base font-semibold text-foreground mb-1">No topics loaded yet</h3>
            <p className="text-sm text-muted-foreground">Run the Supabase migration to seed mentor topics.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {topics.map((topic, i) => {
              const isCompleted = completedTopics.includes(topic.id);
              const mastery = getMastery(topic.id);
              const masteryPct = Math.round(mastery * 100);
              const persona = PERSONAS[topic.mentor_id] || {
                name: 'AI Tutor', domain: 'General', initial: 'AI', color: 'bg-muted-foreground'
              };

              return (
                <motion.div
                  key={topic.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.08 + i * 0.04 }}
                >
                  <button
                    onClick={() => navigate(`/learn/${topic.id}`)}
                    className={`w-full card-base p-5 flex items-center gap-4 text-left hover:bg-muted transition-all duration-150 group ${isCompleted ? 'opacity-80' : ''}`}
                  >
                    {/* Mentor avatar */}
                    <div className={`w-16 h-16 rounded-2xl flex items-center justify-center shrink-0 overflow-hidden ${persona.color}`}>
                      {persona.avatar ? (
                        <img src={persona.avatar} alt={persona.name} className="w-full h-full object-cover" />
                      ) : (
                        <span className="text-white text-xs font-bold tracking-tight">{persona.initial}</span>
                      )}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-sm font-semibold text-foreground truncate">{topic.title}</span>
                      </div>
                      {/* Mentor attribution */}
                      <p className="text-[11px] text-muted-foreground mb-1.5 font-medium">
                        with {persona.name} · {persona.domain}
                      </p>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium border ${getDifficultyColor(getMasteryLabel(mastery))}`}>
                          {getMasteryLabel(mastery)}
                        </span>
                        <span className="pill">{topic.estimated_time ?? 30} min</span>

                      </div>
                    </div>

                    {/* Mastery bar */}
                    {mastery > 0 && (
                      <div className="shrink-0 w-14 hidden sm:block">
                        <div className="progress-track">
                          <div
                            className="h-full rounded-full bg-foreground transition-all"
                            style={{ width: `${masteryPct}%` }}
                          />
                        </div>
                        <p className="text-[10px] text-muted-foreground mt-1 text-right">{masteryPct}%</p>
                      </div>
                    )}

                    {/* Completed indicator or start arrow */}
                    {isCompleted
                      ? <div className="btn-arrow-filled shrink-0"><CheckCircle2 size={13} /></div>
                      : <div className="btn-arrow shrink-0"><ArrowRight size={14} /></div>
                    }
                  </button>
                </motion.div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
};

export default Learn;
