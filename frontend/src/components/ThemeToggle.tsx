import { useTheme } from '@/contexts/ThemeContext';
import { Sun, Moon } from 'lucide-react';

const ThemeToggle = () => {
  const { isDarkMode, toggleDarkMode } = useTheme();
  return (
    <button
      onClick={toggleDarkMode}
      aria-label="Toggle theme"
      className="w-8 h-8 flex items-center justify-center rounded-lg border border-border bg-card text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
    >
      {isDarkMode ? <Sun size={14} /> : <Moon size={14} />}
    </button>
  );
};

export default ThemeToggle;
