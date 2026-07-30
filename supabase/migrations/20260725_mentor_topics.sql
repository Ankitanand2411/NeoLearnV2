-- ============================================================
-- NeoLearn Migration: Remove Math Topics, Add Mentor-Guided Topics
-- Run this in your Supabase SQL Editor
-- ============================================================

-- Step 1: Add mentor_id column to topics table
ALTER TABLE topics ADD COLUMN IF NOT EXISTS mentor_id TEXT DEFAULT '';
ALTER TABLE topics ADD COLUMN IF NOT EXISTS explanation TEXT DEFAULT '';
ALTER TABLE topics ADD COLUMN IF NOT EXISTS key_takeaway TEXT DEFAULT '';

-- Step 2: Clear all existing math topics (and any orphaned progress)
DELETE FROM user_mastery WHERE topic_id IN (SELECT id FROM topics);
DELETE FROM user_progress WHERE topic_id IN (SELECT id FROM topics);
DELETE FROM topics;

-- Step 3: Insert 10 mentor-guided topics
-- Each topic is owned by a historical mentor (mentor_id maps to persona_registry.py)

INSERT INTO topics (title, description, difficulty, mentor_id, explanation, key_takeaway) VALUES

-- Einstein: Physics & Relativity
(
  'Special Relativity: Time and Space',
  'Explore how the speed of light is constant for all observers and what this means for time and space — taught by Albert Einstein.',
  'intermediate',
  'einstein',
  'Special Relativity rests on two postulates: (1) the laws of physics are identical in all inertial reference frames, and (2) the speed of light in a vacuum is c (~3×10^8 m/s) regardless of the observer. Consequences include time dilation (moving clocks run slow), length contraction (moving objects shorten along motion), and the equivalence of mass and energy via E=mc². The Lorentz transformations formally describe how coordinates transform between frames.',
  'Time and space are not absolute — they stretch and compress based on relative velocity. At the speed of light, time stops. Mass and energy are different forms of the same thing.'
),

-- Feynman: Quantum Mechanics
(
  'Quantum Superposition and Measurement',
  'Why does a quantum particle exist in multiple states at once — and why does measuring it collapse everything? Taught by Richard Feynman.',
  'advanced',
  'feynman',
  'A quantum system is described by a wavefunction ψ, which encodes the probability amplitude for all possible states simultaneously (superposition). The act of measurement forces the wavefunction to collapse into one definite outcome. The double-slit experiment demonstrates wave-particle duality: an electron fired at two slits creates an interference pattern — unless you observe which slit it went through, at which point the pattern vanishes. Schrödinger''s equation governs how wavefunctions evolve over time.',
  'Quantum particles do not have definite properties until measured. The act of observation itself changes the outcome. Probability is baked into nature, not a product of our ignorance.'
),

-- Marie Curie: Chemistry
(
  'Radioactivity and Atomic Structure',
  'What is radioactivity, and what does it tell us about the atom? Discovered and explained by Marie Curie.',
  'beginner',
  'curie',
  'Radioactivity is the spontaneous emission of energy from unstable atomic nuclei. Marie Curie identified three types: alpha decay (emission of a helium nucleus, reducing atomic number by 2), beta decay (emission of an electron or positron, changing a neutron to a proton), and gamma radiation (high-energy photons emitted during nuclear transitions). The half-life of a radioactive substance is the time required for half of its nuclei to decay — this is a statistical property of large numbers of atoms.',
  'Atoms are not indivisible — their nuclei are unstable and emit energy. Radioactivity revealed that matter itself has an inner life we could not see before.'
),

-- Socrates: Philosophy
(
  'The Nature of Knowledge and Belief',
  'What does it mean to truly know something versus merely believe it? Examine the foundations of knowledge with Socrates.',
  'beginner',
  'socrates',
  'Epistemology is the branch of philosophy concerned with the nature, origin, and scope of knowledge. Plato''s traditional definition — knowledge is justified true belief (JTB) — requires three conditions: (1) the belief must be true, (2) you must believe it, and (3) you must have justification for it. Edmund Gettier (1963) demonstrated this definition is insufficient with counterexamples where all three conditions are met yet intuitive knowledge is absent. Alternative accounts include reliabilism (a belief counts as knowledge if it arises from a reliable process) and virtue epistemology.',
  'Knowing something requires more than being right — you must also have good reasons. Most of what we call knowledge is really justified belief. True knowledge is harder to achieve than it seems.'
),

-- Alan Turing: Computer Science
(
  'Computation, Algorithms, and the Turing Machine',
  'What is computation, fundamentally? What can and cannot be computed? Explored by Alan Turing.',
  'intermediate',
  'turing',
  'A Turing Machine is an abstract model of computation consisting of: an infinite tape divided into cells, a read/write head, a finite set of states, and a transition function that defines what to do (write a symbol, move left/right, change state) given the current state and symbol. A problem is computable if a Turing Machine can solve it in finite steps. The Halting Problem — deciding whether an arbitrary program halts or loops forever — is proven undecidable: no Turing Machine can solve it for all inputs. Church-Turing thesis: anything that can be algorithmically computed can be computed by a Turing Machine.',
  'Computation has fundamental limits. Some problems are provably unsolvable by any algorithm, no matter how powerful the machine. Turing defined what "computing" means before computers existed.'
),

-- Darwin: Biology
(
  'Natural Selection and Evolutionary Mechanisms',
  'How does complex life arise from simple variation? Understand the mechanism of evolution with Charles Darwin.',
  'beginner',
  'darwin',
  'Natural selection operates through four conditions: (1) Variation — individuals within a population differ in heritable traits. (2) Heritability — traits are passed to offspring. (3) Differential survival/reproduction — some traits increase survival and reproductive success in a given environment. (4) Selection pressure — the environment "selects" which traits persist. Over generations, advantageous traits become more frequent. Speciation occurs when populations become reproductively isolated and diverge sufficiently. The Modern Synthesis integrates Darwinian natural selection with Mendelian genetics and population genetics.',
  'Life changes over time because individuals with advantageous traits survive longer and reproduce more. Complexity arises gradually from small, cumulative changes — not design.'
),

-- Florence Nightingale: Statistics
(
  'Data Distributions and Statistical Inference',
  'How do we draw reliable conclusions from data? Learn to think statistically with Florence Nightingale.',
  'intermediate',
  'nightingale',
  'A probability distribution describes how values of a random variable are spread. The normal (Gaussian) distribution is symmetric and characterized by mean μ and standard deviation σ — 68% of values fall within 1σ of the mean, 95% within 2σ. Statistical inference uses sample data to make claims about populations. A hypothesis test sets up a null hypothesis H₀ and alternative H₁, then calculates a p-value: the probability of observing the data (or more extreme) if H₀ is true. A p-value < 0.05 conventionally warrants rejecting H₀. Effect size and confidence intervals communicate the practical significance beyond binary accept/reject.',
  'Data alone does not speak — you must ask the right question first. Statistical inference lets you make confident claims from limited samples, but only if you understand what the numbers actually measure.'
),

-- Gandhi: Leadership & Ethics
(
  'Non-Violence, Power, and Moral Courage',
  'What makes a leader? Examine the ethics of power and the philosophy of non-violent resistance with Mahatma Gandhi.',
  'beginner',
  'gandhi',
  'Satyagraha (Sanskrit: "truth-force" or "soul-force") is Gandhi''s philosophy of non-violent resistance. It rests on three principles: (1) Ahimsa — non-harm in thought, word, and deed; (2) Satya — commitment to truth even at personal cost; (3) Tapasya — willingness to accept suffering without retaliation. Power, in this framework, is not coercive force but the capacity to mobilize moral authority and voluntary cooperation. Gandhi''s Civil Disobedience campaigns (Salt March, 1930) demonstrate that unjust laws can be resisted publicly and non-violently to delegitimize the oppressor.',
  'True power does not come from force — it comes from moral clarity and the willingness to suffer for a principle. Non-violence is not passivity; it is the most demanding form of courage.'
),

-- Ramanujan: Mathematics
(
  'Number Theory: Primes, Patterns, and Infinite Series',
  'Discover the hidden patterns inside numbers — infinite series, prime distributions, and mathematical beauty with Ramanujan.',
  'advanced',
  'ramanujan',
  'Prime numbers are integers greater than 1 with no divisors other than 1 and themselves. The Prime Number Theorem states that the number of primes less than n is approximately n / ln(n). Ramanujan made extraordinary contributions to the partition function p(n) — the number of ways n can be written as an ordered sum of positive integers — developing asymptotic formulas of stunning accuracy. He discovered that 1/1 + 1/4 + 1/9 + ... (Basel problem) = π²/6, and produced remarkable identities for infinite series and continued fractions, many of which took decades to prove.',
  'Numbers have deep internal structure that goes far beyond arithmetic. Patterns in primes and series connect seemingly unrelated areas of mathematics in surprising ways — and beautiful results often point to profound underlying truths.'
),

-- Mark Twain: Literature
(
  'Voice, Style, and the Craft of Prose',
  'What separates good writing from great writing? Learn the craft of clear, vivid prose with Mark Twain.',
  'beginner',
  'twain',
  'Effective prose relies on several craft principles: (1) Specificity — concrete details outperform vague generalizations ("a beagle with a torn ear" beats "a dog"); (2) Economy — every word must earn its place; passive constructions, redundant modifiers, and throat-clearing phrases weaken sentences; (3) Voice — the distinctive personality that emerges through word choice, sentence rhythm, and what the narrator notices; (4) Show, don''t tell — dramatize emotion through action and dialogue rather than labeling it ("He slammed the door" vs "He was angry"); (5) The right word — synonyms are not interchangeable; precision of diction is everything.',
  'Writing is not decoration — it is thinking made visible. Great prose is specific, economical, and honest. The difference between the right word and the almost-right word is enormous.'
);
