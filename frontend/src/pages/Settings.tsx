import { useState } from 'react';
import { motion } from 'framer-motion';
import { useTheme } from '@/contexts/ThemeContext';
import { useAuth } from '@/contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import Navbar from '@/components/Navbar';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Trash2, Download, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

const SettingRow = ({
  label,
  description,
  children,
}: {
  label: string;
  description: string;
  children: React.ReactNode;
}) => (
  <div className="flex items-center justify-between py-4">
    <div className="min-w-0 pr-4">
      <p className="text-sm font-semibold text-foreground">{label}</p>
      <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{description}</p>
    </div>
    <div className="shrink-0">{children}</div>
  </div>
);

const SectionCard = ({ title, delay, children }: { title: string; delay: number; children: React.ReactNode }) => (
  <motion.div
    initial={{ opacity: 0, y: 14 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay }}
    className="card-base p-6 mb-4"
  >
    <p className="section-label mb-1">{title}</p>
    {children}
  </motion.div>
);

const Settings = () => {
  const { isDarkMode, toggleDarkMode } = useTheme();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [sidebarWidth, setSidebarWidth] = useState(220);

  return (
    <div className="min-h-screen bg-background">
      <Navbar onSidebarWidthChange={setSidebarWidth} />

      <main
        className="px-8 py-8"
        style={{ marginLeft: sidebarWidth, width: `calc(100% - ${sidebarWidth}px)`, transition: 'margin-left 0.25s, width 0.25s' }}
      >
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="mb-10">
          <p className="section-label mb-2">Settings</p>
          <h1 className="heading-display">Preferences</h1>
        </motion.div>

        {/* Appearance */}
        <SectionCard title="Appearance" delay={0.06}>
          <div className="divide-y divide-border">
            <SettingRow label="Dark mode" description="Switch between light and dark interface">
              <Switch id="dark-mode" checked={isDarkMode} onCheckedChange={toggleDarkMode} />
            </SettingRow>
          </div>
        </SectionCard>

        {/* Notifications */}
        <SectionCard title="Notifications" delay={0.1}>
          <div className="divide-y divide-border">
            <SettingRow label="Learning reminders" description="Get reminded to continue your learning streak">
              <Switch id="learning-reminders" defaultChecked />
            </SettingRow>
            <SettingRow label="Achievement notifications" description="Get notified when you earn new badges">
              <Switch id="achievement-notifications" defaultChecked />
            </SettingRow>
            <SettingRow label="Weekly progress" description="Receive weekly progress summaries">
              <Switch id="weekly-progress" defaultChecked />
            </SettingRow>
          </div>
        </SectionCard>

        {/* Account */}
        <SectionCard title="Account" delay={0.14}>
          <div className="mt-3 mb-5 p-4 rounded-xl bg-muted">
            <p className="section-label mb-1">Signed in as</p>
            <p className="text-sm font-semibold text-foreground">{user?.email}</p>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={() => toast.success('Data export coming soon')}
              variant="outline"
              size="sm"
              className="h-9 text-sm rounded-xl"
            >
              <Download size={13} className="mr-1.5" />Export data
            </Button>
            <Button
              onClick={() => navigate('/profile')}
              size="sm"
              className="h-9 text-sm rounded-xl bg-foreground text-background hover:bg-foreground/90"
            >
              Edit profile <ArrowRight size={13} className="ml-1.5" />
            </Button>
          </div>
        </SectionCard>

        {/* Privacy & Security */}
        <SectionCard title="Privacy &amp; Security" delay={0.18}>
          <div className="divide-y divide-border mb-5">
            <SettingRow label="Analytics" description="Help improve NeoLearn by sharing anonymous usage data">
              <Switch id="analytics" defaultChecked />
            </SettingRow>
            <SettingRow label="Personalized recommendations" description="Get topic suggestions based on your progress">
              <Switch id="personalization" defaultChecked />
            </SettingRow>
          </div>
          <div className="pt-4 border-t border-border">
            <Button
              onClick={() => toast.error('Account deletion is not available')}
              variant="outline"
              size="sm"
              className="h-9 text-sm rounded-xl text-destructive border-destructive/30 hover:bg-destructive/5 hover:border-destructive"
            >
              <Trash2 size={13} className="mr-1.5" />Delete account
            </Button>
            <p className="text-xs text-muted-foreground mt-2">
              This action cannot be undone. All your data will be permanently deleted.
            </p>
          </div>
        </SectionCard>

        {/* Footer */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.24 }} className="text-center py-6">
          <p className="text-xs text-muted-foreground">NeoLearn v1.0 · Socratic AI-Powered Adaptive Learning</p>
        </motion.div>
      </main>
    </div>
  );
};

export default Settings;
