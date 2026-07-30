
import { useNavigate, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import TutorAvatar from './TutorAvatar';
import { Home, User, Settings, BookOpen } from 'lucide-react';
import { toast } from 'sonner';

const Navigation = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const userName = localStorage.getItem('userName') || 'Student';

  const handleLogout = () => {
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('userName');
    localStorage.removeItem('userEmail');
    toast.success('Logged out successfully!');
    navigate('/login');
  };

  const navItems = [
    { path: '/dashboard', icon: Home, label: 'Dashboard' },
    { path: '/profile', icon: User, label: 'Profile' },
    { path: '/settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <Card className="bg-white/90 backdrop-blur-sm shadow-lg border-0 m-4">
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <TutorAvatar size="sm" />
            <div>
              <h2 className="font-bold text-gray-900">NeoLearn</h2>
              <p className="text-sm text-gray-600">Hi, {userName}! 👋</p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {navItems.map((item) => (
              <Button
                key={item.path}
                variant={location.pathname === item.path ? "default" : "ghost"}
                size="sm"
                onClick={() => navigate(item.path)}
                className="flex items-center space-x-2"
              >
                <item.icon size={16} />
                <span className="hidden md:inline">{item.label}</span>
              </Button>
            ))}
            
            <Button
              variant="outline"
              size="sm"
              onClick={handleLogout}
              className="text-red-600 hover:text-red-700 hover:bg-red-50"
            >
              Logout
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default Navigation;
