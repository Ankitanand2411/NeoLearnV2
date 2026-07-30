import { useState } from 'react';
import { motion } from 'framer-motion';
import { Navigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { supabase } from '@/integrations/supabase/client';
import { toast } from 'sonner';
import { ArrowUpRight } from 'lucide-react';

const FEATURES = [
  { label: 'Socratic AI Tutor', desc: 'Learn by explaining — the AI probes your understanding' },
  { label: 'Adaptive Quiz Engine', desc: 'Targeted questions that patch your exact knowledge gaps' },
  { label: 'LLM-as-Judge Grading', desc: 'Free-text answers scored with precision by a secondary LLM' },
];

const Login = () => {
  const [loading, setLoading] = useState(false);
  const { user, loading: authLoading } = useAuth();

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="spinner" />
      </div>
    );
  }

  if (user) return <Navigate to="/dashboard" replace />;

  const handleGoogleSignIn = async () => {
    setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/dashboard`,
        },
      });
      if (error) throw error;
    } catch (error: any) {
      toast.error(error.message || 'Google sign-in failed');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col lg:flex-row">
      {/* Left panel — dark editorial */}
      <div
        className="relative hidden lg:flex lg:w-[52%] flex-col justify-between p-12 overflow-hidden"
        style={{ background: 'hsl(0 0% 5%)' }}
      >
        {/* Background grid lines */}
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage: `linear-gradient(hsl(0 0% 80%) 1px, transparent 1px), linear-gradient(90deg, hsl(0 0% 80%) 1px, transparent 1px)`,
            backgroundSize: '48px 48px',
          }}
        />

        {/* Brand */}
        <div className="relative z-10">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-white flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="black" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
                <path d="M6 12v5c3 3 9 3 12 0v-5"/>
              </svg>
            </div>
            <span className="font-semibold text-white text-sm tracking-tight">NeoLearn</span>
          </div>
        </div>

        {/* Center hero text */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10"
        >
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/40 mb-5">
            AI-Powered Learning
          </p>
          <h1 className="text-5xl font-bold leading-[1.1] text-white mb-6 tracking-tight">
            Keep Learning<br />On Track
          </h1>
          <p className="text-white/50 text-base leading-relaxed max-w-xs">
            Elevate your knowledge with cutting-edge Socratic AI. Join NeoLearn for comprehensive, adaptive learning.
          </p>
        </motion.div>

        {/* Feature cards at bottom */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10 flex flex-col gap-2"
        >
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.label}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 + i * 0.08 }}
              className="flex items-start gap-3 p-3 rounded-xl"
              style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)' }}
            >
              <div className="w-1.5 h-1.5 rounded-full bg-white/30 mt-1.5 shrink-0" />
              <div>
                <p className="text-sm font-semibold text-white">{f.label}</p>
                <p className="text-xs text-white/40 mt-0.5">{f.desc}</p>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>

      {/* Right panel — clean sign-in */}
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="w-full max-w-sm"
        >
          {/* Mobile brand */}
          <div className="lg:hidden mb-10 flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-foreground flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="hsl(var(--background))" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
                <path d="M6 12v5c3 3 9 3 12 0v-5"/>
              </svg>
            </div>
            <span className="font-semibold text-foreground text-sm tracking-tight">NeoLearn</span>
          </div>

          {/* Heading */}
          <div className="mb-10">
            <p className="section-label mb-3">Welcome back</p>
            <h2 className="heading-xl mb-2">Sign in to continue</h2>
            <p className="text-muted-foreground text-sm leading-relaxed">
              Your personalized learning journey awaits. One click to get started.
            </p>
          </div>

          {/* Google button */}
          <button
            id="google-signin-btn"
            onClick={handleGoogleSignIn}
            disabled={loading}
            className="w-full flex items-center gap-3 rounded-2xl border border-border bg-card hover:bg-muted transition-all duration-200 text-sm font-medium text-foreground disabled:opacity-50 disabled:cursor-not-allowed group px-5 py-3.5"
          >
            {loading ? (
              <span className="spinner-sm mx-auto" />
            ) : (
              <>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" className="shrink-0">
                  <path d="M17.64 9.20455C17.64 8.56636 17.5827 7.95273 17.4764 7.36364H9V10.845H13.8436C13.635 11.97 13.0009 12.9232 12.0477 13.5614V15.8195H14.9564C16.6582 14.2527 17.64 11.9455 17.64 9.20455Z" fill="#4285F4"/>
                  <path d="M9 18C11.43 18 13.4673 17.1941 14.9564 15.8195L12.0477 13.5614C11.2418 14.1014 10.2109 14.4204 9 14.4204C6.65591 14.4204 4.67182 12.8373 3.96409 10.71H0.957275V13.0418C2.43818 15.9832 5.48182 18 9 18Z" fill="#34A853"/>
                  <path d="M3.96409 10.71C3.78409 10.17 3.68182 9.59318 3.68182 9C3.68182 8.40682 3.78409 7.83 3.96409 7.29V4.95818H0.957275C0.347727 6.17318 0 7.54773 0 9C0 10.4523 0.347727 11.8268 0.957275 13.0418L3.96409 10.71Z" fill="#FBBC05"/>
                  <path d="M9 3.57955C10.3214 3.57955 11.5077 4.03364 12.4405 4.92545L15.0218 2.34409C13.4632 0.891818 11.4259 0 9 0C5.48182 0 2.43818 2.01682 0.957275 4.95818L3.96409 7.29C4.67182 5.16273 6.65591 3.57955 9 3.57955Z" fill="#EA4335"/>
                </svg>
                <span className="flex-1">Continue with Google</span>
                <div className="w-7 h-7 rounded-full border border-border flex items-center justify-center shrink-0 group-hover:bg-foreground group-hover:border-foreground transition-all duration-200">
                  <ArrowUpRight size={13} className="text-muted-foreground group-hover:text-background transition-colors" />
                </div>
              </>
            )}
          </button>

          {/* Divider */}
          <div className="flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-border" />
            <span className="text-[11px] text-muted-foreground uppercase tracking-widest">Secure</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          {/* Trust badges */}
          <div className="grid grid-cols-3 gap-2">
            {['RAG Grounded', 'Socratic AI', 'Adaptive'].map((tag) => (
              <div key={tag} className="pill justify-center">{tag}</div>
            ))}
          </div>

          <p className="mt-8 text-center text-xs text-muted-foreground">
            By continuing, you agree to NeoLearn's terms of service and privacy policy.
          </p>
        </motion.div>
      </div>
    </div>
  );
};

export default Login;
