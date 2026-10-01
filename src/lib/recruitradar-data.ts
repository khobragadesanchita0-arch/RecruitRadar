export type RequirementStatus = "MATCH" | "PARTIAL" | "UNCERTAIN" | "MISSING";

export const roles = [
  { id: "frontend", title: "Senior Frontend Developer", department: "Engineering", resumes: 128, shortlisted: 8, lastRun: "12 min ago", status: "Analysis complete" },
  { id: "backend", title: "Python Backend Developer", department: "Engineering", resumes: 86, shortlisted: 6, lastRun: "Yesterday", status: "Ready to review" },
  { id: "analyst", title: "Data Analyst", department: "Data & Insights", resumes: 54, shortlisted: 4, lastRun: "3 days ago", status: "Draft" },
];

export const requirements: { requirement: string; importance: string; evidence: string; status: RequirementStatus; confidence: number }[] = [
  { requirement: "Production React & TypeScript", importance: "Must have", evidence: "Led migration of a 14-app platform to React and TypeScript.", status: "MATCH", confidence: 96 },
  { requirement: "Design systems ownership", importance: "Must have", evidence: "Built a shared component library used by 11 product teams.", status: "MATCH", confidence: 93 },
  { requirement: "Frontend performance", importance: "Must have", evidence: "Improved LCP by 41% across high-traffic checkout flows.", status: "MATCH", confidence: 91 },
  { requirement: "Team mentorship", importance: "Preferred", evidence: "Mentoring noted, but scope and frequency are not specified.", status: "UNCERTAIN", confidence: 61 },
  { requirement: "GraphQL", importance: "Preferred", evidence: "Apollo Client listed without project-level supporting evidence.", status: "PARTIAL", confidence: 54 },
];

export const candidates = [
  { id: 1, name: "Candidate 017", initials: "C17", role: "Staff Frontend Engineer", score: 92, confidence: 94, experience: "9 years", evidence: 18, skills: ["React", "TypeScript", "Design systems"], noise: 0, summary: "Strong evidence of architecture ownership and measurable performance impact." },
  { id: 2, name: "Candidate 042", initials: "C42", role: "Senior Product Engineer", score: 87, confidence: 89, experience: "7 years", evidence: 15, skills: ["React", "GraphQL", "Mentoring"], noise: 1, summary: "Well-rounded product engineer with clear delivery and mentorship evidence." },
  { id: 3, name: "Candidate 063", initials: "C63", role: "Frontend Platform Engineer", score: 82, confidence: 84, experience: "6 years", evidence: 13, skills: ["TypeScript", "Performance", "Testing"], noise: 2, summary: "Strong platform fundamentals; leadership scope needs verification." },
  { id: 4, name: "Candidate 105", initials: "C105", role: "UI Engineer", score: 76, confidence: 72, experience: "5 years", evidence: 9, skills: ["React", "Accessibility", "CSS"], noise: 1, summary: "Relevant implementation evidence, with limited systems ownership." },
];

export const interviewQuestions = [
  { skill: "Architecture", question: "Tell us about a frontend architecture decision you owned. What trade-offs did you make?", reason: "Validates system-level ownership shown in the resume." },
  { skill: "Performance", question: "How did you measure and improve the 41% LCP reduction?", reason: "Tests the strongest quantified evidence." },
  { skill: "Mentorship", question: "How many engineers did you mentor, and how did you measure their progress?", reason: "Resolves an uncertain preferred requirement." },
  { skill: "Design systems", question: "How did you drive adoption across teams with competing priorities?", reason: "Explores collaboration behind a verified achievement." },
];

export const pipeline = ["JD Analysis", "Resume Analysis", "Skill Normalization", "Evidence Extraction", "Matching", "Noise Detection", "Shortlist", "Interview Kit"];