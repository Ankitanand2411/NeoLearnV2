
import { cn } from '@/lib/utils';

interface TutorAvatarProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const TutorAvatar = ({ size = 'md', className }: TutorAvatarProps) => {
  const sizeClasses = {
    sm: 'w-8 h-8 text-lg',
    md: 'w-12 h-12 text-2xl',
    lg: 'w-20 h-20 text-4xl'
  };

  return (
    <div className={cn(
      'rounded-full bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center shadow-lg animate-pulse',
      sizeClasses[size],
      className
    )}>
      <span className="text-white">🦉</span>
    </div>
  );
};

export default TutorAvatar;
