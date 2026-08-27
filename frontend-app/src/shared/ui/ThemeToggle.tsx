import React from 'react';
import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

interface Props { className?: string }

const ThemeToggle: React.FC<Props> = ({ className = '' }) => {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';
  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className={`ds-theme-pill ${className}`}
    >
      <span className="ds-theme-thumb">
        {isDark
          ? <Moon style={{ width: 10, height: 10, color: '#fff' }} />
          : <Sun  style={{ width: 10, height: 10, color: '#fff' }} />}
      </span>
    </button>
  );
};

export default ThemeToggle;
