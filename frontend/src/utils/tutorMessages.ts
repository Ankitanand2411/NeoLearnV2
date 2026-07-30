
import { motivationalQuotes } from '@/data/mockData';

export const getRandomMotivationalMessage = (studentName: string): string => {
  const greetings = [
    `Hello ${studentName}! Ready to explore the amazing world of math today? 🤗`,
    `Welcome back, ${studentName}! Your brain is like a muscle - let's make it stronger! 💪`,
    `Hey ${studentName}! Every mathematician started exactly where you are now. Let's learn! 📚`,
    `Hi ${studentName}! Mathematics is all around us. Ready to discover its secrets? 🔍`,
    `Good to see you, ${studentName}! Remember, every problem you solve is a victory! 🏆`
  ];
  
  return greetings[Math.floor(Math.random() * greetings.length)];
};

export const getTopicCompletionMessage = (topicTitle: string): string => {
  const messages = [
    `🎉 Fantastic work on ${topicTitle}! You've really mastered this concept!`,
    `🌟 Excellent job completing ${topicTitle}! Your understanding is growing stronger!`,
    `🏆 Bravo! You've conquered ${topicTitle}! Ready for the next challenge?`,
    `💯 Outstanding work on ${topicTitle}! You're becoming a math superstar!`,
    `🚀 Amazing progress on ${topicTitle}! You're building real mathematical skills!`
  ];
  
  return messages[Math.floor(Math.random() * messages.length)];
};

export const getNextTopicMessage = (nextTopicTitle: string): string => {
  const messages = [
    `🎯 Based on your progress, I recommend ${nextTopicTitle} next! It builds perfectly on what you've learned!`,
    `📈 You're ready for ${nextTopicTitle}! This is the perfect next step in your learning journey!`,
    `⭐ Time for ${nextTopicTitle}! You have all the foundation you need to succeed!`,
    `🧠 ${nextTopicTitle} is calling your name! Let's tackle this exciting new challenge!`,
    `🌟 Your next adventure awaits: ${nextTopicTitle}! I know you'll do great!`
  ];
  
  return messages[Math.floor(Math.random() * messages.length)];
};

export const getEncouragementMessage = (): string => {
  return motivationalQuotes[Math.floor(Math.random() * motivationalQuotes.length)];
};

export const getQuizFeedback = (isCorrect: boolean, attempts: number): string => {
  if (isCorrect) {
    const successMessages = [
      "🎉 Perfect! You nailed it!",
      "🌟 Excellent work! You've got this!",
      "💯 Outstanding! Your understanding is solid!",
      "🏆 Brilliant! You're really getting the hang of this!",
      "🚀 Amazing! You solved it perfectly!"
    ];
    return successMessages[Math.floor(Math.random() * successMessages.length)];
  } else {
    if (attempts === 1) {
      return "🤔 Not quite right, but that's totally okay! Learning happens through trying. Want to give it another shot?";
    } else if (attempts === 2) {
      return "💪 You're getting closer! Sometimes the best learning happens when we work through challenges together.";
    } else {
      return "📚 Let's review the explanation together. Every mathematician learns by building understanding step by step!";
    }
  }
};
