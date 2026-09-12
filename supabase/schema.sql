-- NeoLearn Supabase Database Schema
-- Paste this script into your Supabase SQL Editor to initialize the database.

-- Create topics table
CREATE TABLE IF NOT EXISTS public.topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    difficulty TEXT,
    explanation TEXT,
    icon TEXT,
    key_takeaway TEXT,
    prerequisites TEXT[] DEFAULT '{}',
    quiz_correct_answer TEXT,
    quiz_options TEXT[] DEFAULT '{}',
    quiz_question TEXT,
    video_description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS for topics
ALTER TABLE public.topics ENABLE ROW LEVEL SECURITY;

-- Check if policy exists before creating
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'topics' AND policyname = 'Allow public read access to topics'
    ) THEN
        CREATE POLICY "Allow public read access to topics" ON public.topics FOR SELECT USING (true);
    END IF;
END $$;

-- Create profiles table
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    username TEXT,
    full_name TEXT,
    avatar TEXT DEFAULT '🧑‍🎓',
    avatar_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS for profiles
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'profiles' AND policyname = 'Allow public read access to profiles'
    ) THEN
        CREATE POLICY "Allow public read access to profiles" ON public.profiles FOR SELECT USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'profiles' AND policyname = 'Allow individual write access to profiles'
    ) THEN
        CREATE POLICY "Allow individual write access to profiles" ON public.profiles FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
    END IF;
END $$;

-- Create user_progress table
CREATE TABLE IF NOT EXISTS public.user_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    topic_id UUID NOT NULL REFERENCES public.topics(id) ON DELETE CASCADE,
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(user_id, topic_id)
);

-- Enable RLS for user_progress
ALTER TABLE public.user_progress ENABLE ROW LEVEL SECURITY;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'user_progress' AND policyname = 'Allow individual read access to progress'
    ) THEN
        CREATE POLICY "Allow individual read access to progress" ON public.user_progress FOR SELECT USING (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'user_progress' AND policyname = 'Allow individual insert access to progress'
    ) THEN
        CREATE POLICY "Allow individual insert access to progress" ON public.user_progress FOR INSERT WITH CHECK (auth.uid() = user_id);
    END IF;
END $$;

-- Create user_badges table
CREATE TABLE IF NOT EXISTS public.user_badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    badge_name TEXT NOT NULL,
    earned_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS for user_badges
ALTER TABLE public.user_badges ENABLE ROW LEVEL SECURITY;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'user_badges' AND policyname = 'Allow individual read access to badges'
    ) THEN
        CREATE POLICY "Allow individual read access to badges" ON public.user_badges FOR SELECT USING (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'user_badges' AND policyname = 'Allow individual insert access to badges'
    ) THEN
        CREATE POLICY "Allow individual insert access to badges" ON public.user_badges FOR INSERT WITH CHECK (auth.uid() = user_id);
    END IF;
END $$;

-- Create user_mastery table
CREATE TABLE IF NOT EXISTS public.user_mastery (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    topic_id UUID NOT NULL REFERENCES public.topics(id) ON DELETE CASCADE,
    mastery_level DOUBLE PRECISION DEFAULT 0.0 NOT NULL,
    questions_attempted INTEGER DEFAULT 0 NOT NULL,
    questions_correct INTEGER DEFAULT 0 NOT NULL,
    last_attempted_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(user_id, topic_id)
);

-- Enable RLS for user_mastery
ALTER TABLE public.user_mastery ENABLE ROW LEVEL SECURITY;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'user_mastery' AND policyname = 'Allow public read access to mastery'
    ) THEN
        CREATE POLICY "Allow public read access to mastery" ON public.user_mastery FOR SELECT USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'user_mastery' AND policyname = 'Allow individual write access to mastery'
    ) THEN
        CREATE POLICY "Allow individual write access to mastery" ON public.user_mastery FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
    END IF;
END $$;

-- Create user_streaks table
CREATE TABLE IF NOT EXISTS public.user_streaks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    current_streak INTEGER DEFAULT 0 NOT NULL,
    longest_streak INTEGER DEFAULT 0 NOT NULL,
    last_activity_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS for user_streaks
ALTER TABLE public.user_streaks ENABLE ROW LEVEL SECURITY;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'user_streaks' AND policyname = 'Allow individual read access to streaks'
    ) THEN
        CREATE POLICY "Allow individual read access to streaks" ON public.user_streaks FOR SELECT USING (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'user_streaks' AND policyname = 'Allow individual write access to streaks'
    ) THEN
        CREATE POLICY "Allow individual write access to streaks" ON public.user_streaks FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
    END IF;
END $$;

-- Create the leaderboard_top5 view
CREATE OR REPLACE VIEW public.leaderboard_top5 AS
SELECT 
    p.user_id,
    p.username,
    p.avatar,
    COALESCE(AVG(m.mastery_level), 0.0) as avg_mastery
FROM public.profiles p
LEFT JOIN public.user_mastery m ON p.user_id = m.user_id
GROUP BY p.user_id, p.username, p.avatar
ORDER BY avg_mastery DESC
LIMIT 5;

-- Create update_mastery_level function
CREATE OR REPLACE FUNCTION public.update_mastery_level(
    user_uuid UUID,
    topic_uuid UUID,
    is_correct BOOLEAN
)
RETURNS DOUBLE PRECISION
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    current_mastery DOUBLE PRECISION;
    new_mastery DOUBLE PRECISION;
    attempted INTEGER;
    correct INTEGER;
BEGIN
    -- Check if record exists
    SELECT mastery_level, questions_attempted, questions_correct
    INTO current_mastery, attempted, correct
    FROM public.user_mastery
    WHERE user_id = user_uuid AND topic_id = topic_uuid;

    IF NOT FOUND THEN
        attempted := 1;
        IF is_correct THEN
            correct := 1;
            new_mastery := 0.2; -- Initial correct answer gives 20% mastery
        ELSE
            correct := 0;
            new_mastery := 0.0;
        END IF;

        INSERT INTO public.user_mastery (user_id, topic_id, mastery_level, questions_attempted, questions_correct, last_attempted_at)
        VALUES (user_uuid, topic_uuid, new_mastery, attempted, correct, now());
    ELSE
        attempted := attempted + 1;
        IF is_correct THEN
            correct := correct + 1;
            -- Mastery increases faster when correct
            new_mastery := LEAST(current_mastery + 0.15, 1.0);
        ELSE
            -- Mastery decreases when incorrect
            new_mastery := GREATEST(current_mastery - 0.1, 0.0);
        END IF;

        UPDATE public.user_mastery
        SET mastery_level = new_mastery,
            questions_attempted = attempted,
            questions_correct = correct,
            last_attempted_at = now(),
            updated_at = now()
        WHERE user_id = user_uuid AND topic_id = topic_uuid;
    END IF;

    RETURN new_mastery;
END;
$$;

-- Create update_user_streak function
CREATE OR REPLACE FUNCTION public.update_user_streak(
    user_uuid UUID
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    streak_record RECORD;
    today_date DATE := CURRENT_DATE;
BEGIN
    SELECT * INTO streak_record
    FROM public.user_streaks
    WHERE user_id = user_uuid;

    IF NOT FOUND THEN
        INSERT INTO public.user_streaks (user_id, current_streak, longest_streak, last_activity_date)
        VALUES (user_uuid, 1, 1, today_date);
    ELSE
        IF streak_record.last_activity_date = today_date THEN
            -- Already active today, streak remains same
            RETURN;
        ELSIF streak_record.last_activity_date = today_date - 1 THEN
            -- Active yesterday, increment streak
            UPDATE public.user_streaks
            SET current_streak = current_streak + 1,
                longest_streak = GREATEST(longest_streak, current_streak + 1),
                last_activity_date = today_date,
                updated_at = now()
            WHERE user_id = user_uuid;
        ELSE
            -- Streak broken
            UPDATE public.user_streaks
            SET current_streak = 1,
                last_activity_date = today_date,
                updated_at = now()
            WHERE user_id = user_uuid;
        END IF;
    END IF;
END;
$$;

-- Insert Seed Data for Topics
INSERT INTO public.topics (id, title, description, difficulty, explanation, icon, key_takeaway, prerequisites, quiz_correct_answer, quiz_options, quiz_question, video_description)
VALUES
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Algebra Basics', 'Learn the foundation of algebra, including variables, expressions, and simple equations.', 'Beginner', 'Algebra uses letters (like x or y) to represent numbers in equations. You can solve for these variables by performing the same operations on both sides of the equation.', '🧮', 'Maintain equation balance: whatever you do to one side, you must do to the other.', ARRAY['None'], 'x = 5', ARRAY['x = 3', 'x = 5', 'x = 7', 'x = 10'], 'Solve for x: 2x + 4 = 14', 'Introductory tutorial on linear expressions and solving basic equations.')
    ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title;

INSERT INTO public.topics (id, title, description, difficulty, explanation, icon, key_takeaway, prerequisites, quiz_correct_answer, quiz_options, quiz_question, video_description)
VALUES
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12', 'Linear Equations', 'Master graphing and solving equations that form straight lines.', 'Intermediate', 'Linear equations represent relationships with a constant rate of change. They can be written in slope-intercept form: y = mx + b, where m is the slope and b is the y-intercept.', '📈', 'The slope represents the rate of change, and the y-intercept is where the line crosses the y-axis.', ARRAY['Algebra Basics'], 'y = 2x + 3', ARRAY['y = x + 2', 'y = 2x + 3', 'y = 3x - 1', 'y = -2x + 5'], 'What is the equation of the line with slope 2 and y-intercept 3?', 'Understanding slope-intercept form and graphing lines on a coordinate plane.')
    ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title;

INSERT INTO public.topics (id, title, description, difficulty, explanation, icon, key_takeaway, prerequisites, quiz_correct_answer, quiz_options, quiz_question, video_description)
VALUES
    ('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13', 'Quadratic Equations', 'Dive into second-degree polynomial equations and their parabolic graphs.', 'Intermediate', 'Quadratic equations contain a squared variable (x^2). They can be solved using factoring, completing the square, or the quadratic formula: x = (-b ± √(b^2 - 4ac)) / 2a.', '📐', 'The solutions (roots) of a quadratic equation are the x-intercepts of its parabolic graph.', ARRAY['Linear Equations'], 'x = 2 or x = 3', ARRAY['x = 1 or x = 5', 'x = 2 or x = 3', 'x = -2 or x = -3', 'x = 0 or x = 6'], 'Solve the quadratic equation: x^2 - 5x + 6 = 0', 'Explaining factoring techniques and the quadratic formula visually.')
    ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title;

INSERT INTO public.topics (id, title, description, difficulty, explanation, icon, key_takeaway, prerequisites, quiz_correct_answer, quiz_options, quiz_question, video_description)
VALUES
    ('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a14', 'Geometry Basics', 'Explore properties of shapes, angles, area, and perimeter.', 'Beginner', 'Geometry is the study of shapes, sizes, and space. Key concepts include angles (acute, right, obtuse), perimeter (distance around a shape), and area (space inside a shape).', '📐', 'The sum of angles in any triangle is always 180 degrees.', ARRAY['None'], '180 degrees', ARRAY['90 degrees', '180 degrees', '270 degrees', '360 degrees'], 'What is the sum of angles in a triangle?', 'Visual introduction to points, lines, angles, and basic geometric shapes.')
    ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title;

INSERT INTO public.topics (id, title, description, difficulty, explanation, icon, key_takeaway, prerequisites, quiz_correct_answer, quiz_options, quiz_question, video_description)
VALUES
    ('e0eebc99-9c0b-4ef8-bb6d-6bb9bd380a15', 'Trigonometry', 'Study the relationships between the side lengths and angles of triangles.', 'Advanced', 'Trigonometry focuses on right-angled triangles using functions like Sine (opposite/hypotenuse), Cosine (adjacent/hypotenuse), and Tangent (opposite/adjacent) - remembered as SOH CAH TOA.', '📐', 'Trigonometric functions help calculate distances and angles that are otherwise hard to measure.', ARRAY['Geometry Basics', 'Linear Equations'], '0.5', ARRAY['0.0', '0.5', '0.707', '1.0'], 'What is the value of sin(30 degrees)?', 'Introduction to sine, cosine, tangent, and unit circle concepts.')
    ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title;
