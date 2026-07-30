
export interface Topic {
  id: string;
  title: string;
  difficulty: 'Beginner' | 'Intermediate' | 'Advanced';
  estimatedTime: string;
  description: string;
  prerequisites: string[];
  videoDescription: string;
  explanation: string;
  keyTakeaway: string;
  quiz: {
    question: string;
    options: string[];
    correctAnswer: string;
  };
}

export interface Student {
  id: string;
  name: string;
  email: string;
  completedTopics: string[];
  currentStreak: number;
  badges: string[];
  avatar: string;
}

export const mockTopics: Topic[] = [
  {
    id: 'algebra-basics',
    title: 'Algebra Basics',
    difficulty: 'Beginner',
    estimatedTime: '15 minutes',
    description: 'Learn the fundamentals of algebra including variables and basic operations.',
    prerequisites: [],
    videoDescription: 'An introduction to algebra covering variables, coefficients, and basic algebraic expressions.',
    explanation: 'Algebra is the branch of mathematics that uses letters and symbols to represent numbers and quantities in formulas and equations. In algebra, we use variables (like x, y, or z) to represent unknown values that we want to find.',
    keyTakeaway: 'Variables are placeholders for unknown numbers, and algebraic expressions combine variables with numbers using mathematical operations.',
    quiz: {
      question: 'What is the value of x in the equation: x + 5 = 12?',
      options: ['5', '7', '8', '17'],
      correctAnswer: '7'
    }
  },
  {
    id: 'linear-equations',
    title: 'Linear Equations',
    difficulty: 'Beginner',
    estimatedTime: '20 minutes',
    description: 'Master solving linear equations with one variable.',
    prerequisites: ['algebra-basics'],
    videoDescription: 'Learn step-by-step methods for solving linear equations and checking your solutions.',
    explanation: 'Linear equations are equations where the highest power of the variable is 1. They form straight lines when graphed. To solve linear equations, we use inverse operations to isolate the variable on one side of the equation.',
    keyTakeaway: 'Use inverse operations (opposite operations) to isolate the variable and find its value.',
    quiz: {
      question: 'Solve for x: 3x - 6 = 15',
      options: ['3', '7', '9', '21'],
      correctAnswer: '7'
    }
  },
  {
    id: 'quadratics',
    title: 'Quadratic Equations',
    difficulty: 'Intermediate',
    estimatedTime: '25 minutes',
    description: 'Explore quadratic equations and different methods to solve them.',
    prerequisites: ['linear-equations'],
    videoDescription: 'Understanding quadratic equations, factoring, and using the quadratic formula.',
    explanation: 'Quadratic equations are polynomial equations of degree 2, meaning the highest power of the variable is 2. They can be solved using factoring, completing the square, or the quadratic formula.',
    keyTakeaway: 'Quadratic equations have the form ax² + bx + c = 0 and can have zero, one, or two real solutions.',
    quiz: {
      question: 'What are the solutions to x² - 5x + 6 = 0?',
      options: ['x = 2, x = 3', 'x = 1, x = 6', 'x = -2, x = -3', 'x = 0, x = 5'],
      correctAnswer: 'x = 2, x = 3'
    }
  },
  {
    id: 'functions',
    title: 'Introduction to Functions',
    difficulty: 'Intermediate',
    estimatedTime: '30 minutes',
    description: 'Understand what functions are and how to work with them.',
    prerequisites: ['linear-equations'],
    videoDescription: 'Exploring functions, domain and range, and function notation.',
    explanation: 'A function is a special relationship where each input has exactly one output. Functions can be represented using equations, graphs, tables, or verbal descriptions. Function notation f(x) means "f of x" or "the function f applied to x".',
    keyTakeaway: 'Functions create a unique output for every input, establishing predictable mathematical relationships.',
    quiz: {
      question: 'If f(x) = 2x + 3, what is f(4)?',
      options: ['8', '11', '14', '5'],
      correctAnswer: '11'
    }
  },
  {
    id: 'graphing',
    title: 'Graphing Functions',
    difficulty: 'Advanced',
    estimatedTime: '35 minutes',
    description: 'Learn to graph linear and quadratic functions.',
    prerequisites: ['functions', 'quadratics'],
    videoDescription: 'Creating graphs of functions and understanding their visual representations.',
    explanation: 'Graphing functions helps us visualize mathematical relationships. Linear functions create straight lines, while quadratic functions create parabolas. The graph shows how the output (y-value) changes as the input (x-value) changes.',
    keyTakeaway: 'Graphs provide a visual way to understand function behavior and find solutions to equations.',
    quiz: {
      question: 'What is the y-intercept of the function y = 2x + 5?',
      options: ['2', '5', '0', '-5'],
      correctAnswer: '5'
    }
  },
  {
    id: 'systems',
    title: 'Systems of Equations',
    difficulty: 'Advanced',
    estimatedTime: '40 minutes',
    description: 'Solve systems of linear equations using multiple methods.',
    prerequisites: ['linear-equations', 'graphing'],
    videoDescription: 'Methods for solving systems including substitution, elimination, and graphing.',
    explanation: 'A system of equations is a set of two or more equations with the same variables. The solution is the point where all equations intersect. Systems can be solved by substitution, elimination, or graphing methods.',
    keyTakeaway: 'Systems of equations help solve real-world problems involving multiple constraints and relationships.',
    quiz: {
      question: 'What is the solution to the system: x + y = 5 and x - y = 1?',
      options: ['(3, 2)', '(2, 3)', '(4, 1)', '(1, 4)'],
      correctAnswer: '(3, 2)'
    }
  }
];

export const mockStudent: Student = {
  id: 'student-1',
  name: 'Alex',
  email: 'alex@example.com',
  completedTopics: ['algebra-basics'],
  currentStreak: 3,
  badges: ['First Steps'],
  avatar: '🧑‍🎓'
};

export const motivationalQuotes = [
  "Every expert was once a beginner! 🌟",
  "Mathematics is not about numbers, equations, computations, or algorithms: it is about understanding! 🧠",
  "The only way to learn mathematics is to do mathematics! 💪",
  "You're not just learning math, you're training your brain to think logically! 🔥",
  "Every problem you solve makes you stronger! Keep going! 🚀",
  "Mistakes are proof that you are trying! Don't give up! ✨",
  "Math is like a puzzle - each piece you learn helps complete the picture! 🧩",
  "You're doing amazing! One step at a time leads to big achievements! 🏆"
];
