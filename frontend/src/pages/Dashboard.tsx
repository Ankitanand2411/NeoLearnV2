import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/contexts/AuthContext';
import Navbar from '@/components/Navbar';
import { BookOpen, Trophy, Flame, TrendingUp, ArrowRight, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';
import type { Topic } from '@/types/Topic';
import Leaderboard from '@/components/Leaderboard';
import { motion } from 'framer-motion';

const Dashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [nextTopic, setNextTopic] = useState<Topic | null>(null);
  const [stats, setStats] = useState({ completedTopics: 0, totalTopics: 0, currentStreak: 0, badges: 0 });
  const [userProfile, setUserProfile] = useState<{ full_name?: string; username?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(220);

  useEffect(() => {
    const fetchDashboardData = async () => {
      if (!user) return;
      try {
        const { data: profileData } = await supabase.from('profiles').select('full_name, username').eq('user_id', user.id).single();
        if (profileData) setUserProfile(profileData);

        const { data: topicsData } = await supabase.from('topics').select('*');
        const { data: progressData } = await supabase.from('user_progress').select('topic_id').eq('user_id', user.id);
        const { data: badgesData } = await supabase.from('user_badges').select('badge_name').eq('user_id', user.id);
        const { data: streakData } = await supabase.from('user_streaks').select('current_streak').eq('user_id', user.id).single();

        const completedTopicIds = progressData?.map((p) => p.topic_id) || [];
        const incompleteTopic = topicsData?.find((topic) => !completedTopicIds.includes(topic.id));
        if (incompleteTopic) setNextTopic({ ...incompleteTopic, estimated_time: 30 });

        setStats({
          completedTopics: completedTopicIds.length,
          totalTopics: topicsData?.length || 0,
          currentStreak: streakData?.current_streak || 0,
          badges: badgesData?.length || 0,
        });
      } catch {
        toast.error('Failed to load dashboard');
      } finally {
        setLoading(false);
      }
    };
    fetchDashboardData();
  }, [user]);

  const displayName = userProfile?.full_name || userProfile?.username || user?.email?.split('@')[0] || 'there';
  const progress = stats.totalTopics > 0 ? Math.round((stats.completedTopics / stats.totalTopics) * 100) : 0;

  const statCards = [
    { label: 'Topics done', value: `${stats.completedTopics}`, sub: `of ${stats.totalTopics}`, icon: BookOpen },
    { label: 'Current streak', value: `${stats.currentStreak}`, sub: 'days', icon: Flame },
    { label: 'Badges earned', value: `${stats.badges}`, sub: 'achievements', icon: Trophy },
    { label: 'Overall progress', value: `${progress}%`, sub: 'complete', icon: TrendingUp },
  ];

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

  return (
    <div className="min-h-screen bg-background">
      <Navbar onSidebarWidthChange={setSidebarWidth} />

      <main
        className="px-8 py-8"
        style={{ marginLeft: sidebarWidth, width: `calc(100% - ${sidebarWidth}px)`, transition: 'margin-left 0.25s, width 0.25s' }}
      >
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="mb-10">
          <p className="section-label mb-2">Dashboard</p>
          <h1 className="heading-display mb-2">
            Hello, {displayName}
          </h1>
          <p className="text-muted-foreground text-sm">Here's where you left off.</p>
        </motion.div>

        {/* Stats grid */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.06 }}
          className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6"
        >
          {statCards.map(({ label, value, sub, icon: Icon }, i) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.08 + i * 0.05 }}
              className="card-base p-5"
            >
              <div className="flex items-center justify-between mb-5">
                <span className="section-label">{label}</span>
                <div className="w-8 h-8 rounded-xl bg-muted flex items-center justify-center shrink-0">
                  <Icon size={14} className="text-muted-foreground" />
                </div>
              </div>
              <p className="text-2xl font-bold text-foreground tracking-tight leading-none">{value}</p>
              <p className="text-xs text-muted-foreground mt-2">{sub}</p>
            </motion.div>
          ))}
        </motion.div>

        {/* Progress bar card */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.12 }}
          className="card-base p-6 mb-6"
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="section-label mb-1">Course progress</p>
              <p className="text-sm text-muted-foreground">{stats.completedTopics} of {stats.totalTopics} topics completed</p>
            </div>
            <span className="text-4xl font-bold text-foreground tracking-tight">{progress}%</span>
          </div>
          <div className="progress-track">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ delay: 0.5, duration: 1, ease: 'easeOut' }}
              className="progress-fill"
            />
          </div>
        </motion.div>

        {/* Continue learning */}
        {nextTopic && (
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.16 }}
            className="card-base p-6 mb-6"
          >
            <p className="section-label mb-4">Continue learning</p>
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <h3 className="text-lg font-bold text-foreground mb-1 truncate">{nextTopic.title}</h3>
                <p className="text-sm text-muted-foreground mb-3 line-clamp-1">{nextTopic.description}</p>
                <div className="flex gap-2">
                  <span className="pill">{nextTopic.difficulty}</span>
                  <span className="pill">{nextTopic.estimated_time} min</span>
                </div>
              </div>
              <button
                onClick={() => navigate(`/learn/${nextTopic.id}`)}
                className="btn-arrow-filled shrink-0"
                aria-label="Start topic"
              >
                <ArrowRight size={16} />
              </button>
            </div>
          </motion.div>
        )}



        {/* Leaderboard */}
        <motion.div id="leaderboard" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.24 }}>
          <Leaderboard />
        </motion.div>
      </main>
    </div>
  );
};

export default Dashboard;
