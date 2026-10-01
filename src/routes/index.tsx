import { createFileRoute } from "@tanstack/react-router";
import { LandingPage } from "@/components/landing-page";

export const Route = createFileRoute("/")({
  head: () => ({ meta: [
    { title: "RecruitRadar — Evidence-first recruitment intelligence" },
    { name: "description", content: "Turn resumes into explainable, evidence-backed shortlists without keyword scoring." },
    { property: "og:title", content: "RecruitRadar — Evidence-first recruitment intelligence" },
    { property: "og:description", content: "Turn resumes into explainable, evidence-backed shortlists without keyword scoring." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: LandingPage,
});
