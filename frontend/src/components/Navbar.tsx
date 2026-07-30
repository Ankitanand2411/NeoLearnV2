import { motion } from 'framer-motion';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import { useNavigate, useLocation } from 'react-router-dom';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Home, User, Settings, LogOut, Sun, Moon, BookOpen, GraduationCap } from 'lucide-react';
import { toast } from 'sonner';
import React, { useState, useEffect } from 'react';

interface NavbarProps {
  onSidebarWidthChange?: (width: number) => void;
}

const SIDEBAR_WIDTH = 220;

const Navbar = ({ onSidebarWidthChange }: NavbarProps) => {
  const { user, signOut } = useAuth();
  const { isDarkMode, toggleDarkMode } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();

  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  useEffect(() => {
    if (onSidebarWidthChange) {
      onSidebarWidthChange(!isMobile && isSidebarOpen ? SIDEBAR_WIDTH : 0);
    }
  }, [onSidebarWidthChange, isMobile, isSidebarOpen]);

  const handleNavigation = (path: string) => {
    navigate(path);
    if (isMobile) setIsSidebarOpen(false);
  };

  const handleSignOut = async () => {
    try {
      await signOut();
      toast.success('Signed out');
      navigate('/login');
    } catch {
      toast.error('Failed to sign out');
    }
  };

  const navItems = [
    { path: '/dashboard', icon: Home, label: 'Dashboard' },
    { path: '/learn', icon: BookOpen, label: 'Learn' },
    { path: '/profile', icon: User, label: 'Profile' },
    { path: '/settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <>
      {/* Mobile toggle */}
      {isMobile && (
        <button
          aria-label={isSidebarOpen ? 'Close menu' : 'Open menu'}
          onClick={() => setIsSidebarOpen((o) => !o)}
          className="fixed top-4 left-4 z-[100] w-9 h-9 flex items-center justify-center rounded-xl border border-border bg-card text-foreground shadow-sm md:hidden"
        >
          <svg width={15} height={15} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            {isSidebarOpen
              ? <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              : <path strokeLinecap="round" strokeLinejoin="round" d="M4 8h16M4 16h16" />}
          </svg>
        </button>
      )}

      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={{ x: isSidebarOpen ? 0 : -300, opacity: isSidebarOpen ? 1 : 0 }}
        transition={{ type: 'spring', stiffness: 320, damping: 32 }}
        className={`fixed top-0 left-0 h-full z-50 bg-card border-r border-border flex flex-col ${isMobile && !isSidebarOpen ? 'pointer-events-none' : ''}`}
        style={{ width: isMobile ? Math.min(240, window.innerWidth * 0.75) : SIDEBAR_WIDTH }}
      >
        {/* Logo */}
        <div className="h-16 flex items-center px-5 border-b border-border">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-foreground flex items-center justify-center shrink-0">
              <GraduationCap size={14} className="text-background" />
            </div>
            <div>
              <span className="font-bold text-foreground text-sm tracking-tight">NeoLearn</span>
              <p className="text-[10px] text-muted-foreground leading-none mt-0.5">AI Tutor</p>
            </div>
          </div>
        </div>

        {/* Nav items */}
        <nav className="flex-1 px-3 py-5 flex flex-col gap-0.5 overflow-y-auto">
          <p className="px-2 mb-3 section-label">Navigation</p>
          {navItems.map((item) => {
            const isActive = location.pathname === item.path || location.pathname.startsWith(item.path + '/');
            return (
              <Tooltip key={item.path}>
                <TooltipTrigger asChild>
                  <button
                    onClick={() => handleNavigation(item.path)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 text-left ${
                      isActive
                        ? 'bg-foreground text-background'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                    }`}
                  >
                    <item.icon size={15} className="shrink-0" />
                    <span className="hidden md:inline">{item.label}</span>
                    {isActive && (
                      <span className="hidden md:inline ml-auto w-1.5 h-1.5 rounded-full bg-background/40" />
                    )}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right"><p>{item.label}</p></TooltipContent>
              </Tooltip>
            );
          })}
        </nav>

        {/* Bottom controls */}
        <div className="px-3 py-4 border-t border-border flex flex-col gap-0.5">
          {/* User info snippet */}
          {user?.email && (
            <div className="px-3 py-2 mb-2 rounded-xl bg-muted">
              <p className="text-[10px] text-muted-foreground truncate">{user.email}</p>
            </div>
          )}
          <button
            onClick={toggleDarkMode}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-all duration-150"
          >
            {isDarkMode ? <Sun size={15} className="shrink-0" /> : <Moon size={15} className="shrink-0" />}
            <span className="hidden md:inline">{isDarkMode ? 'Light mode' : 'Dark mode'}</span>
          </button>
          <button
            onClick={handleSignOut}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-muted-foreground hover:text-destructive hover:bg-destructive/5 transition-all duration-150"
          >
            <LogOut size={15} className="shrink-0" />
            <span className="hidden md:inline">Sign out</span>
          </button>
        </div>
      </motion.aside>
    </>
  );
};

export default Navbar;
