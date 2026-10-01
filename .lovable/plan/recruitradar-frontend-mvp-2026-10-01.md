# RecruitRadar frontend MVP

## Goal
Build the complete evidence-first recruitment workspace described in the PRD, with stored user profiles and polished responsive interactions.

## What I’ll build
- A public RecruitRadar home page plus sign-in, sign-up, and password recovery flows.
- Stored user profiles with secure access rules.
- A roles workspace with search, filters, role creation, realistic demo roles, and settings.
- The three-pane Evidence Desk with role/run navigation, Brief, Pool, Shortlist, Compare, and Interview Kit views.
- Reusable evidence, confidence, status, noise, candidate, command, loading, empty, and notification elements.
- Working mock interactions for uploads, analysis controls, candidate inspection, comparison, filtering, and Blind Mode.
- Responsive layouts for desktop, tablet, and mobile with accessible controls and focus states.

## Product rules
- Keyword presence contributes zero scoring weight.
- Uncertain evidence remains distinct from missing evidence.
- Blind Mode defaults on and consistently hides unnecessary candidate identity.
- Only structured recruiter-facing evidence and explanations are shown.
- No non-MVP integrations or features will be added.

## Technical details
- Use the existing React/TanStack application architecture with TypeScript and Tailwind.
- Enable Lovable Cloud for authentication and persistent profiles.
- Keep recruitment data mocked behind a clear data layer for later backend replacement.
- Give every public page unique sharing and search metadata.
- Validate the final result in the live preview across desktop and mobile sizes.
