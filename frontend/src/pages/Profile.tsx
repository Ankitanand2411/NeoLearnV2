import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/contexts/AuthContext';
import Navbar from '@/components/Navbar';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { BookOpen, Trophy, Pencil, Upload, CheckCircle2, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

interface Profile { username: string; full_name: string; avatar: string; avatar_url?: string; }
interface Badge { id: string; badge_name: string; earned_at: string; }

const Profile = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [profile, setProfile] = useState<Profile>({ username: '', full_name: '', avatar: 'U', avatar_url: undefined });
  const [badges, setBadges] = useState<Badge[]>([]);
  const [completedTopics, setCompletedTopics] = useState(0);
  const [totalTopics, setTotalTopics] = useState(0);
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(220);

  useEffect(() => {
    const fetchProfile = async () => {
      if (!user) return;
      try {
        const { data: profileData, error: profileError } = await supabase.from('profiles').select('*').eq('user_id', user.id).single();
        if (profileError && profileError.code !== 'PGRST116') console.error(profileError);
        if (profileData) {
          setProfile({
            username: profileData.username || user.email?.split('@')[0] || '',
            full_name: profileData.full_name || '',
            avatar: profileData.avatar || user.email?.[0]?.toUpperCase() || 'U',
            avatar_url: profileData.avatar_url || undefined,
          });
        } else {
          const defaultProfile = { user_id: user.id, username: user.email?.split('@')[0] || '', full_name: '', avatar: user.email?.[0]?.toUpperCase() || 'U', avatar_url: null };
          await supabase.from('profiles').insert(defaultProfile);
          setProfile({ username: defaultProfile.username, full_name: '', avatar: defaultProfile.avatar, avatar_url: undefined });
        }
        const { data: badgesData } = await supabase.from('user_badges').select('*').eq('user_id', user.id).order('earned_at', { ascending: false });
        const { data: progressData } = await supabase.from('user_progress').select('*').eq('user_id', user.id);
        const { data: topicsData } = await supabase.from('topics').select('id');
        setBadges(badgesData || []);
        setCompletedTopics(progressData?.length || 0);
        setTotalTopics(topicsData?.length || 0);
      } catch {
        toast.error('Failed to load profile');
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, [user]);

  const handleSaveProfile = async () => {
    if (!user) return;
    try {
      const { error } = await supabase.from('profiles').upsert(
        { user_id: user.id, username: profile.username, full_name: profile.full_name, avatar: profile.avatar, avatar_url: profile.avatar_url, updated_at: new Date().toISOString() },
        { onConflict: 'user_id' }
      );
      if (error) throw error;
      toast.success('Profile saved');
      setIsEditing(false);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to save');
    }
  };

  const handleAvatarUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !user) return;
    if (file.size > 2 * 1024 * 1024) { toast.error('File must be under 2MB'); return; }
    if (!file.type.startsWith('image/')) { toast.error('Select an image file'); return; }
    setUploading(true);
    try {
      const fileExt = file.name.split('.').pop();
      const fileName = `${user.id}/avatar.${fileExt}`;
      const { error: uploadError } = await supabase.storage.from('avatars').upload(fileName, file, { upsert: true });
      if (uploadError) throw uploadError;
      const { data } = supabase.storage.from('avatars').getPublicUrl(fileName);
      setProfile((prev) => ({ ...prev, avatar_url: data.publicUrl }));
      toast.success('Avatar updated');
    } catch {
      toast.error('Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const progress = totalTopics > 0 ? Math.round((completedTopics / totalTopics) * 100) : 0;
  const displayName = profile.full_name || profile.username || user?.email?.split('@')[0] || 'User';

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

      <main className="px-8 py-8" style={{ marginLeft: sidebarWidth, width: `calc(100% - ${sidebarWidth}px)`, transition: 'margin-left 0.25s, width 0.25s' }}>
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="mb-10">
          <p className="section-label mb-2">Account</p>
          <h1 className="heading-display">Profile</h1>
        </motion.div>

        {/* Profile card */}
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 }} className="card-base p-6 mb-5">
          <div className="flex items-start gap-5">
            {/* Avatar */}
            <div className="relative shrink-0">
              <Avatar className="w-16 h-16 rounded-2xl">
                {profile.avatar_url && <AvatarImage src={profile.avatar_url} alt="Avatar" />}
                <AvatarFallback className="bg-foreground text-background text-lg font-bold rounded-2xl">
                  {profile.avatar?.[0]?.toUpperCase() || displayName[0]?.toUpperCase()}
                </AvatarFallback>
              </Avatar>
              {isEditing && (
                <label htmlFor="avatar-upload" className="absolute -bottom-1 -right-1 w-6 h-6 bg-foreground rounded-full flex items-center justify-center cursor-pointer hover:opacity-80 transition-opacity">
                  <Upload size={10} className="text-background" />
                  <input id="avatar-upload" type="file" accept="image/*" onChange={handleAvatarUpload} disabled={uploading} className="sr-only" />
                </label>
              )}
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              {isEditing ? (
                <div className="space-y-3">
                  <div>
                    <Label className="section-label mb-1.5 block">Full name</Label>
                    <Input value={profile.full_name} onChange={(e) => setProfile({ ...profile, full_name: e.target.value })} placeholder="Your full name" className="h-9 text-sm rounded-xl" />
                  </div>
                  <div>
                    <Label className="section-label mb-1.5 block">Username</Label>
                    <Input value={profile.username} onChange={(e) => setProfile({ ...profile, username: e.target.value })} placeholder="Username" className="h-9 text-sm rounded-xl" />
                  </div>
                  <div className="flex gap-2 pt-1">
                    <Button onClick={handleSaveProfile} size="sm" className="h-8 text-xs rounded-xl bg-foreground text-background hover:bg-foreground/90">Save</Button>
                    <Button onClick={() => setIsEditing(false)} variant="outline" size="sm" className="h-8 text-xs rounded-xl">Cancel</Button>
                  </div>
                </div>
              ) : (
                <div>
                  <h2 className="text-xl font-bold text-foreground">{displayName}</h2>
                  {profile.full_name && <p className="text-sm text-muted-foreground">@{profile.username}</p>}
                  <p className="text-sm text-muted-foreground">{user?.email}</p>
                </div>
              )}
            </div>

            {!isEditing && (
              <button onClick={() => setIsEditing(true)} className="btn-arrow shrink-0">
                <Pencil size={13} />
              </button>
            )}
          </div>
        </motion.div>

        {/* Stats */}
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="grid grid-cols-3 gap-3 mb-5">
          {[
            { label: 'Topics Completed', value: completedTopics, icon: BookOpen },
            { label: 'Badges Earned', value: badges.length, icon: Trophy },
            { label: 'Progress', value: `${progress}%`, icon: CheckCircle2 },
          ].map(({ label, value, icon: Icon }) => (
            <div key={label} className="card-base p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="section-label">{label}</span>
                <Icon size={13} className="text-muted-foreground" />
              </div>
              <p className="text-3xl font-bold text-foreground tracking-tight">{value}</p>
            </div>
          ))}
        </motion.div>

        {/* Badges */}
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.14 }} className="card-base p-6">
          <div className="flex items-center justify-between mb-5">
            <p className="section-label">Badges</p>
            <span className="pill">{badges.length} earned</span>
          </div>
          {badges.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {badges.map((badge) => (
                <div key={badge.id} className="flex items-center gap-3 p-3 rounded-xl bg-muted">
                  <div className="w-9 h-9 rounded-xl bg-foreground flex items-center justify-center shrink-0">
                    <Trophy size={13} className="text-background" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-foreground truncate">{badge.badge_name}</p>
                    <p className="text-[11px] text-muted-foreground">{new Date(badge.earned_at).toLocaleDateString()}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-10">
              <div className="w-12 h-12 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
                <Trophy size={20} className="text-muted-foreground" />
              </div>
              <p className="text-sm font-semibold text-foreground mb-1">No badges yet</p>
              <p className="text-sm text-muted-foreground mb-4">Complete topics to earn your first achievement.</p>
              <button
                onClick={() => navigate('/learn')}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-foreground text-background text-sm font-medium hover:opacity-90 transition-opacity"
              >
                Start learning <ArrowRight size={14} />
              </button>
            </div>
          )}
        </motion.div>
      </main>
    </div>
  );
};

export default Profile;
