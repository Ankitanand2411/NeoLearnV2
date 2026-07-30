
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface TopicCardProps {
  topic: {
    id: string;
    title: string;
    difficulty: string;
    estimatedTime: string;
    description: string;
    prerequisites: string[];
  };
  onStart: (topicId: string) => void;
  isCompleted?: boolean;
  isLocked?: boolean;
  isRecommended?: boolean;
}

const TopicCard = ({ topic, onStart, isCompleted, isLocked, isRecommended }: TopicCardProps) => {
  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty.toLowerCase()) {
      case 'beginner': return 'bg-green-100 text-green-800';
      case 'intermediate': return 'bg-yellow-100 text-yellow-800';
      case 'advanced': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <Card className={cn(
      'transition-all duration-200 hover:shadow-lg',
      isCompleted && 'bg-green-50 border-green-200',
      isLocked && 'opacity-50 bg-gray-50',
      isRecommended && 'border-2 border-yellow-400 shadow-md bg-white'
    )}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-lg flex items-center gap-2">
              {isCompleted && '✅'}
              {isLocked && '🔒'}
              {isRecommended && '⭐'}
              {topic.title}
            </CardTitle>
            <CardDescription className="mt-1">
              {topic.description}
            </CardDescription>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 mt-3">
          <Badge variant="secondary" className={getDifficultyColor(topic.difficulty)}>
            {topic.difficulty}
          </Badge>
          <Badge variant="outline" className="text-xs">
            ⏱️ {topic.estimatedTime}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <Button
          onClick={() => onStart(topic.id)}
          disabled={isLocked}
          className={cn(
            'w-full',
            isCompleted && 'bg-green-600 hover:bg-green-700',
            isRecommended && 'bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-600 hover:to-orange-600'
          )}
        >
          {isCompleted ? 'Review Topic' : isLocked ? 'Complete Prerequisites' : 'Start Learning'}
        </Button>
      </CardContent>
    </Card>
  );
};

export default TopicCard;
