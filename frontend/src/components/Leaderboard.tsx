import { useEffect, useState } from 'react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { supabase } from '@/integrations/supabase/client';

type LeaderboardUser = {
  user_id: string;
  username: string | null;
  full_name: string | null;
  avatar: string | null;
  avatar_url: string | null;
  avg_mastery: number;
};

export default function Leaderboard() {
  const [leaders, setLeaders] = useState<LeaderboardUser[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchLeaderboard = async () => {
      setLoading(true);
      try {
        const { data: viewData, error: viewError } = await supabase
          .from('leaderboard_top5')
          .select('*')
          .order('avg_mastery', { ascending: false });

        if (!viewError && viewData && viewData.length > 0) {
          setLeaders(viewData.map((item) => ({
            user_id: item.user_id || '',
            username: item.username,
            full_name: null,
            avatar: item.avatar,
            avatar_url: null,
            avg_mastery: item.avg_mastery || 0,
          })));
          setLoading(false);
          return;
        }

        // Fallback: manual
        const { data: profiles } = await supabase.from('profiles').select('user_id, username, full_name, avatar, avatar_url');
        const { data: masteryData } = await supabase.from('user_mastery').select('user_id, mastery_level');

        if (!profiles || profiles.length === 0) { setLeaders([]); setLoading(false); return; }

        const map = new Map();
        profiles.forEach((p: any) => map.set(p.user_id, { ...p, total: 0, count: 0 }));
        masteryData?.forEach((m: any) => {
          const u = map.get(m.user_id);
          if (u) { u.total += m.mastery_level; u.count += 1; }
        });

        const result = Array.from(map.values())
          .map((u: any) => ({ user_id: u.user_id, username: u.username, full_name: u.full_name, avatar: u.avatar, avatar_url: u.avatar_url, avg_mastery: u.count > 0 ? u.total / u.count : 0 }))
          .sort((a, b) => b.avg_mastery - a.avg_mastery)
          .slice(0, 5);
        setLeaders(result);
      } catch {
        setLeaders([]);
      }
      setLoading(false);
    };
    fetchLeaderboard();
  }, []);

  const getDisplayName = (u: LeaderboardUser) => u.full_name?.trim() || u.username?.trim() || 'Anonymous';
  const getInitial = (u: LeaderboardUser) => {
    const name = getDisplayName(u);
    return name !== 'Anonymous' ? name[0].toUpperCase() : 'A';
  };

  const RANK_SUFFIX = ['st', 'nd', 'rd', 'th', 'th'];

  return (
    <div className="card-base p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="section-label mb-1">Leaderboard</p>
          <p className="text-xs text-muted-foreground">Top 5 by mastery score</p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-10">
          <div className="spinner" />
        </div>
      ) : leaders.length === 0 ? (
        <div className="text-center py-10">
          <p className="text-sm font-semibold text-foreground mb-1">No entries yet</p>
          <p className="text-sm text-muted-foreground">Be the first to complete a topic.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          {leaders.map((user, idx) => {
            const mastery = (user.avg_mastery * 100).toFixed(1);
            const isFirst = idx === 0;
            return (
              <div
                key={user.user_id}
                className={`flex items-center gap-4 px-4 py-3 rounded-xl transition-colors ${isFirst ? 'bg-foreground' : 'bg-muted/50 hover:bg-muted'}`}
              >
                {/* Rank */}
                <div className="w-8 text-center shrink-0">
                  <span className={`text-sm font-bold ${isFirst ? 'text-background' : 'text-muted-foreground'}`}>
                    {idx + 1}<span className="text-[10px]">{RANK_SUFFIX[idx]}</span>
                  </span>
                </div>

                {/* Avatar */}
                <Avatar className="w-8 h-8 rounded-xl shrink-0">
                  {user.avatar_url && <AvatarImage src={user.avatar_url} alt={getDisplayName(user)} />}
                  <AvatarFallback className={`text-xs font-bold rounded-xl ${isFirst ? 'bg-background/20 text-background' : 'bg-foreground text-background'}`}>
                    {getInitial(user)}
                  </AvatarFallback>
                </Avatar>

                {/* Name */}
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-semibold truncate ${isFirst ? 'text-background' : 'text-foreground'}`}>
                    {getDisplayName(user)}
                  </p>
                  {user.username && user.full_name && (
                    <p className={`text-[11px] truncate ${isFirst ? 'text-background/60' : 'text-muted-foreground'}`}>
                      @{user.username}
                    </p>
                  )}
                </div>

                {/* Mastery */}
                <div className="shrink-0 text-right">
                  <p className={`text-base font-bold tracking-tight ${isFirst ? 'text-background' : 'text-foreground'}`}>
                    {mastery}%
                  </p>
                  <p className={`text-[11px] ${isFirst ? 'text-background/60' : 'text-muted-foreground'}`}>mastery</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
