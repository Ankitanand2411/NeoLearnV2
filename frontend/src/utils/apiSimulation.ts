
// This simulates the external recommendation API
// In a real app, this would be replaced with actual API calls

interface RecommendationResponse {
  nextTopic: string;
  message: string;
  confidence: number;
}

export const simulateRecommendationAPI = async (
  completedTopicId: string,
  allCompletedTopics: string[]
): Promise<RecommendationResponse> => {
  // Simulate API delay
  await new Promise(resolve => setTimeout(resolve, 800));

  // Simple recommendation logic (in real app, this would be ML-powered)
  const topicProgression = {
    'algebra-basics': 'linear-equations',
    'linear-equations': 'quadratics',
    'quadratics': 'functions',
    'functions': 'graphing',
    'graphing': 'systems'
  };

  const nextTopicId = topicProgression[completedTopicId] || 'functions';
  
  // Mock response similar to what a real ML API might return
  const response: RecommendationResponse = {
    nextTopic: nextTopicId,
    message: generateRecommendationMessage(nextTopicId, allCompletedTopics.length),
    confidence: Math.random() * 0.3 + 0.7 // 70-100% confidence
  };

  console.log('🤖 Recommendation API Response:', response);
  
  return response;
};

const generateRecommendationMessage = (nextTopic: string, completedCount: number): string => {
  const topicTitles = {
    'linear-equations': 'Linear Equations',
    'quadratics': 'Quadratic Equations',
    'functions': 'Introduction to Functions',
    'graphing': 'Graphing Functions',
    'systems': 'Systems of Equations'
  };

  const title = topicTitles[nextTopic] || 'Next Topic';
  
  if (completedCount <= 1) {
    return `🌟 Great start! ${title} is the perfect next step to build on your foundation!`;
  } else if (completedCount <= 3) {
    return `🚀 You're making excellent progress! ${title} will challenge you in the best way!`;
  } else {
    return `🏆 You're becoming a math expert! ${title} will showcase your growing skills!`;
  }
};

// Simulate updating student progress
export const updateStudentProgress = async (
  studentId: string,
  completedTopicId: string
): Promise<{ success: boolean; newBadges?: string[] }> => {
  await new Promise(resolve => setTimeout(resolve, 500));
  
  const completedTopics = JSON.parse(localStorage.getItem('completedTopics') || '[]');
  const newTotal = completedTopics.length;
  
  // Award badge every 3 topics
  const newBadges = [];
  if (newTotal % 3 === 0 && newTotal > 0) {
    newBadges.push(`Level ${Math.floor(newTotal / 3)} Master`);
  }
  
  return {
    success: true,
    newBadges: newBadges.length > 0 ? newBadges : undefined
  };
};

// Simulate fetching student analytics
export const getStudentAnalytics = async (studentId: string) => {
  await new Promise(resolve => setTimeout(resolve, 300));
  
  const completedTopics = JSON.parse(localStorage.getItem('completedTopics') || '[]');
  
  return {
    totalTopicsCompleted: completedTopics.length,
    currentStreak: Math.floor(Math.random() * 10) + 1,
    averageScore: Math.floor(Math.random() * 20) + 80, // 80-100%
    timeSpentLearning: Math.floor(Math.random() * 300) + 120, // minutes
    badgesEarned: Math.floor(completedTopics.length / 3),
    strongestAreas: ['Algebra', 'Problem Solving'],
    suggestedFocus: ['Graphing', 'Advanced Topics']
  };
};
