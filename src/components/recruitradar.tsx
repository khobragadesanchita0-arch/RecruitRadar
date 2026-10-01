import { Link, useNavigate } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { BriefcaseBusiness, ChevronRight, CircleAlert, CircleCheck, Eye, EyeOff, FileSearch, Gauge, Menu, MoreHorizontal, Pause, Play, Plus, Search, Settings, ShieldCheck, SlidersHorizontal, Sparkles, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { candidates, interviewQuestions, pipeline, requirements, roles, type RequirementStatus } from "@/lib/recruitradar-data";

export function Brand({ compact = false }: { compact?: boolean }) {
  return <Link to="/" className="inline-flex items-center gap-2 font-display text-lg font-semibold text-foreground"><span className="grid size-8 place-items-center rounded-md bg-primary text-primary-foreground"><Gauge className="size-4" /></span>{compact ? null : "RecruitRadar"}</Link>;
}

export function StatusBadge({ status }: { status: RequirementStatus | string }) {
  const tone = status === "MATCH" || status.includes("complete") ? "verified" : status === "UNCERTAIN" || status === "PARTIAL" || status.includes("review") ? "uncertain" : status === "MISSING" ? "danger" : "neutral";
  return <span className={`status-badge status-${tone}`}>{status}</span>;
}

export function ConfidenceRing({ value }: { value: number }) {
  return <div className="confidence-ring" style={{ "--confidence": `${value * 3.6}deg` } as React.CSSProperties}><span>{value}</span></div>;
}

export function EvidenceChip({ children }: { children: React.ReactNode }) {
  return <span className="evidence-chip"><CircleCheck className="size-3.5" />{children}</span>;
}

export function NoiseBadge({ count }: { count: number }) {
  if (!count) return <span className="text-xs text-muted-foreground">No flags</span>;
  return <span className="noise-badge"><CircleAlert className="size-3.5" />{count} noise {count === 1 ? "flag" : "flags"}</span>;
}

export function AppHeader({ blind, onBlindChange, onMenu }: { blind: boolean; onBlindChange: (v: boolean) => void; onMenu: () => void }) {
  return <header className="sticky top-0 z-40 flex h-16 items-center border-b border-border bg-background/95 px-4 backdrop-blur md:px-6">
    <Button variant="ghost" size="icon" className="mr-2 lg:hidden" onClick={onMenu} aria-label="Open navigation"><Menu /></Button>
    <Brand />
    <div className="ml-auto flex items-center gap-3">
      <div className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2"><EyeOff className="size-4 text-muted-foreground" /><Label htmlFor="blind" className="hidden text-xs sm:block">Blind mode</Label><Switch id="blind" checked={blind} onCheckedChange={onBlindChange} /></div>
      <TooltipProvider><Tooltip><TooltipTrigger asChild><Button variant="ghost" size="icon" asChild><Link to="/settings"><Settings /></Link></Button></TooltipTrigger><TooltipContent>Settings</TooltipContent></Tooltip></TooltipProvider>
      <div className="grid size-9 place-items-center rounded-full bg-secondary font-semibold text-secondary-foreground">SK</div>
    </div>
  </header>;
}

function AppNav({ open, onClose }: { open: boolean; onClose: () => void }) {
  return <aside className={`app-sidebar ${open ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0`}>
    <div className="flex items-center justify-between px-4 py-4 lg:hidden"><span className="text-sm font-semibold">Workspace</span><Button variant="ghost" size="icon" onClick={onClose}><X /></Button></div>
    <nav className="space-y-1 px-3 py-4">
      <Link to="/roles" className="nav-item" activeProps={{ className: "nav-item nav-item-active" }}><BriefcaseBusiness />All roles</Link>
      <p className="px-3 pb-2 pt-6 text-xs font-semibold uppercase text-muted-foreground">Active roles</p>
      {roles.map((role) => <Link key={role.id} to="/role/$roleId/brief" params={{ roleId: role.id }} onClick={onClose} className="role-nav"><span className="truncate">{role.title}</span><span>{role.resumes}</span></Link>)}
    </nav>
    <div className="mt-auto border-t border-border p-4"><p className="text-xs leading-5 text-muted-foreground">Evidence, not keywords.<br />Human decisions stay final.</p></div>
  </aside>;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [blind, setBlind] = useState(true);
  const [menu, setMenu] = useState(false);
  return <div className="min-h-screen bg-background"><AppHeader blind={blind} onBlindChange={(v) => { setBlind(v); toast.success(v ? "Blind Mode enabled" : "Blind Mode disabled"); }} onMenu={() => setMenu(true)} />
    <AppNav open={menu} onClose={() => setMenu(false)} />
    {menu && <button aria-label="Close navigation" className="fixed inset-0 z-20 bg-overlay lg:hidden" onClick={() => setMenu(false)} />}
    <main className="lg:pl-64">{children}</main>
  </div>;
}

export function CreateRoleDialog() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button><Plus />Create new role</Button></DialogTrigger><DialogContent>
    <DialogHeader><DialogTitle>Create a new role</DialogTitle><DialogDescription>Add the hiring brief. You can review extracted requirements before analysis.</DialogDescription></DialogHeader>
    <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); setOpen(false); toast.success("Role created"); navigate({ to: "/role/$roleId/brief", params: { roleId: "frontend" } }); }}>
      <div><Label htmlFor="title">Job title</Label><Input id="title" className="mt-2" required placeholder="e.g. Senior Frontend Developer" /></div>
      <div><Label htmlFor="department">Department</Label><Input id="department" className="mt-2" required placeholder="e.g. Engineering" /></div>
      <div><Label htmlFor="description">Job description</Label><Textarea id="description" className="mt-2 min-h-40" required placeholder="Paste the complete job description…" /></div>
      <Button type="submit" className="w-full">Create role</Button>
    </form>
  </DialogContent></Dialog>;
}

export function RolesPage() {
  const [query, setQuery] = useState("");
  const filtered = roles.filter((r) => `${r.title} ${r.department}`.toLowerCase().includes(query.toLowerCase()));
  return <AppShell><div className="page-wrap"><div className="page-heading"><div><p className="eyebrow">Recruitment workspace</p><h1>Your roles</h1><p>Review active searches and continue from the latest evidence run.</p></div><CreateRoleDialog /></div>
    <div className="toolbar"><div className="relative flex-1"><Search className="input-icon" /><Input aria-label="Search roles" value={query} onChange={(e) => setQuery(e.target.value)} className="pl-10" placeholder="Search roles or departments" /></div><Button variant="outline"><SlidersHorizontal />All statuses</Button></div>
    <div className="grid gap-4 xl:grid-cols-3">{filtered.map((role) => <Link key={role.id} to="/role/$roleId/brief" params={{ roleId: role.id }} className="role-card"><div className="flex items-start justify-between"><span className="icon-tile"><BriefcaseBusiness /></span><Button variant="ghost" size="icon" aria-label="Role menu" onClick={(e) => e.preventDefault()}><MoreHorizontal /></Button></div><div><p className="text-xs text-muted-foreground">{role.department}</p><h2 className="mt-1 text-lg font-semibold">{role.title}</h2></div><div className="grid grid-cols-2 gap-4 border-y border-border py-4"><Metric label="Resumes" value={role.resumes} /><Metric label="Shortlisted" value={role.shortlisted} /></div><div className="flex items-center justify-between"><StatusBadge status={role.status} /><span className="text-xs text-muted-foreground">{role.lastRun}</span></div></Link>)}</div>
  </div></AppShell>;
}

function Metric({ label, value }: { label: string; value: string | number }) { return <div><p className="text-2xl font-semibold">{value}</p><p className="text-xs text-muted-foreground">{label}</p></div>; }

function CommandBar({ running, setRunning }: { running: boolean; setRunning: (v: boolean) => void }) {
  return <div className="command-bar"><div className="flex min-w-0 items-center gap-2"><span className={running ? "pulse-dot" : "idle-dot"} /><span className="truncate text-sm font-medium">{running ? "Analyzing 128 resumes" : "Analysis ready"}</span></div><div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => setRunning(!running)}>{running ? <Pause /> : <Play />}{running ? "Pause" : "Run"}</Button><Button size="sm" variant="ghost" onClick={() => { setRunning(false); toast("Run cancelled"); }}>Cancel</Button></div></div>;
}

function AgentLens({ running }: { running: boolean }) {
  return <aside className="agent-lens"><div className="flex items-center gap-2"><Sparkles className="size-4 text-primary" /><h2 className="font-semibold">Agent Lens</h2></div><p className="mt-1 text-xs text-muted-foreground">Structured analysis trace</p><div className="mt-6 space-y-1">{pipeline.map((step, i) => { const done = i < (running ? 5 : 8); const active = running && i === 5; return <div className="pipeline-step" key={step}><span className={done ? "step-done" : active ? "step-active" : "step-wait"}>{done ? <CircleCheck /> : <span>{i + 1}</span>}</span><div><p className="text-sm font-medium">{step}</p><p className="text-xs text-muted-foreground">{done ? "Complete" : active ? "Inspecting signals" : "Waiting"}</p></div></div>; })}</div><div className="mt-6 rounded-md border border-border bg-secondary p-3"><p className="text-xs font-semibold">Scoring principle</p><p className="mt-1 text-xs leading-5 text-muted-foreground">Keyword presence carries zero weight. Scores require contextual evidence.</p></div></aside>;
}

const tabs = [
  ["Brief", "/role/$roleId/brief"], ["Pool", "/role/$roleId/pool"], ["Shortlist", "/role/$roleId/shortlist"], ["Compare", "/role/$roleId/compare"], ["Interview Kit", "/role/$roleId/interview-kit"],
] as const;

export function EvidenceDesk({ roleId, active, children }: { roleId: string; active: string; children: React.ReactNode }) {
  const [running, setRunning] = useState(false);
  return <AppShell><div className="desk-grid"><section className="min-w-0"><div className="desk-top"><div><p className="eyebrow">Engineering · Active role</p><h1>Senior Frontend Developer</h1></div><StatusBadge status={running ? "Analysis running" : "Analysis complete"} /></div><CommandBar running={running} setRunning={setRunning} /><div className="tabs-scroll">{tabs.map(([label, to]) => <Link key={label} to={to} params={{ roleId }} className={active === label ? "desk-tab desk-tab-active" : "desk-tab"}>{label}</Link>)}</div><div className="workspace-content">{children}</div></section><AgentLens running={running} /></div></AppShell>;
}

export function BriefPage({ roleId }: { roleId: string }) {
  return <EvidenceDesk roleId={roleId} active="Brief"><div className="section-heading"><div><h2>Role brief</h2><p>Requirements extracted from the job description for recruiter review.</p></div><Button onClick={() => toast.success("Analysis started")}><Sparkles />Run analysis</Button></div><div className="summary-grid"><Summary label="Required skills" value="6" detail="React, TypeScript, systems" /><Summary label="Preferred skills" value="4" detail="GraphQL, mentoring" /><Summary label="Experience" value="6+ yrs" detail="Production frontend" /></div><section className="content-block"><h3>Requirement matrix</h3><div className="table-wrap"><table><thead><tr><th>Requirement</th><th>Importance</th><th>Evidence</th><th>Status</th><th>Confidence</th></tr></thead><tbody>{requirements.map((r) => <tr key={r.requirement}><td className="font-medium">{r.requirement}</td><td>{r.importance}</td><td className="max-w-sm text-muted-foreground">{r.evidence}</td><td><StatusBadge status={r.status} /></td><td><div className="flex items-center gap-2"><Progress value={r.confidence} className="w-16" /><span className="text-xs">{r.confidence}%</span></div></td></tr>)}</tbody></table></div></section></EvidenceDesk>;
}

function Summary({ label, value, detail }: { label: string; value: string; detail: string }) { return <div className="summary"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-2 text-2xl font-semibold">{value}</p><p className="mt-1 text-xs text-muted-foreground">{detail}</p></div>; }

export function CandidateCard({ candidate, blind, onOpen, selectable, selected, onSelect }: { candidate: typeof candidates[number]; blind: boolean; onOpen: () => void; selectable?: boolean; selected?: boolean; onSelect?: () => void }) {
  return <article className={`candidate-card ${selected ? "candidate-selected" : ""}`}><div className="flex items-start gap-3"><div className="candidate-avatar">{blind ? candidate.initials : candidate.name.slice(0, 2)}</div><div className="min-w-0 flex-1"><p className="font-semibold">{blind ? candidate.name : `Alex Morgan ${candidate.id}`}</p><p className="truncate text-xs text-muted-foreground">{candidate.role} · {candidate.experience}</p></div><ConfidenceRing value={candidate.score} /></div><p className="text-sm leading-6 text-muted-foreground">{candidate.summary}</p><div className="flex flex-wrap gap-2">{candidate.skills.map((s) => <EvidenceChip key={s}>{s}</EvidenceChip>)}</div><div className="flex items-center justify-between border-t border-border pt-3"><span className="text-xs text-muted-foreground">{candidate.evidence} evidence points</span><NoiseBadge count={candidate.noise} /></div><div className="grid grid-cols-2 gap-2">{selectable && <Button variant={selected ? "default" : "outline"} onClick={onSelect}>{selected ? "Selected" : "Compare"}</Button>}<Button variant="outline" className={selectable ? "" : "col-span-2"} onClick={onOpen}>Inspect evidence<ChevronRight /></Button></div></article>;
}

function CandidateDrawer({ candidate, open, onClose }: { candidate: typeof candidates[number] | null; open: boolean; onClose: () => void }) {
  if (!candidate) return null;
  return <>{open && <button className="fixed inset-0 z-50 bg-overlay" aria-label="Close candidate details" onClick={onClose} />}<aside className={`candidate-drawer ${open ? "translate-x-0" : "translate-x-full"}`}><div className="flex items-center justify-between border-b border-border p-5"><div><p className="eyebrow">Evidence profile</p><h2 className="text-xl font-semibold">{candidate.name}</h2></div><Button size="icon" variant="ghost" onClick={onClose}><X /></Button></div><div className="space-y-6 overflow-y-auto p-5"><div className="flex items-center gap-4"><ConfidenceRing value={candidate.confidence} /><div><p className="font-medium">High confidence</p><p className="text-sm text-muted-foreground">{candidate.evidence} grounded evidence points</p></div></div>{requirements.slice(0, 4).map((r, i) => <div key={r.requirement} className="evidence-quote"><div className="flex items-center justify-between gap-2"><p className="font-medium">{r.requirement}</p><StatusBadge status={i === 3 ? "UNCERTAIN" : "MATCH"} /></div><blockquote>“{r.evidence}”</blockquote><p>Resume · Experience section</p></div>)}<div className="rounded-md border border-warning/30 bg-warning-soft p-4"><p className="text-sm font-semibold">Recruiter check</p><p className="mt-1 text-sm text-muted-foreground">Confirm mentorship scope during interview. The evidence is present but not specific enough to verify.</p></div></div></aside></>;
}

export function PoolPage({ roleId, shortlist = false }: { roleId: string; shortlist?: boolean }) {
  const [query, setQuery] = useState(""); const [drawer, setDrawer] = useState<typeof candidates[number] | null>(null); const [uploading, setUploading] = useState(false);
  const visible = candidates.filter((c) => (!shortlist || c.score >= 82) && `${c.name} ${c.skills.join(" ")}`.toLowerCase().includes(query.toLowerCase()));
  const upload = () => { setUploading(true); window.setTimeout(() => { setUploading(false); toast.success("4 resumes added to the pool"); }, 1100); };
  return <EvidenceDesk roleId={roleId} active={shortlist ? "Shortlist" : "Pool"}><div className="section-heading"><div><h2>{shortlist ? "Explainable shortlist" : "Resume pool"}</h2><p>{shortlist ? "Candidates ranked by requirement evidence and confidence." : "128 resumes · PDF, DOCX, and TXT supported"}</p></div>{!shortlist && <Button onClick={upload}><Upload />Upload resumes</Button>}</div>{!shortlist && <button className="upload-zone" onClick={upload}><Upload className="size-6" /><span className="font-medium">Drop resumes here or choose files</span><span className="text-xs text-muted-foreground">PDF, DOCX, TXT · up to 20 MB each</span>{uploading && <Progress value={72} className="mt-2 max-w-xs" />}</button>}<div className="toolbar"><div className="relative flex-1"><Search className="input-icon" /><Input className="pl-10" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search evidence or skills" /></div><Button variant="outline"><SlidersHorizontal />Evidence filters</Button></div><div className="candidate-grid">{visible.map((c) => <CandidateCard key={c.id} candidate={c} blind onOpen={() => setDrawer(c)} />)}</div><CandidateDrawer candidate={drawer} open={!!drawer} onClose={() => setDrawer(null)} /></EvidenceDesk>;
}

export function ComparePage({ roleId }: { roleId: string }) {
  const [drawer, setDrawer] = useState<typeof candidates[number] | null>(null); const pair = candidates.slice(0, 2);
  return <EvidenceDesk roleId={roleId} active="Compare"><div className="section-heading"><div><h2>Candidate comparison</h2><p>Side-by-side evidence against the same role requirements.</p></div><Button variant="outline"><Plus />Add candidate</Button></div><div className="compare-grid">{pair.map((c) => <div key={c.id} className="compare-column"><CandidateCard candidate={c} blind onOpen={() => setDrawer(c)} /><div className="space-y-3">{requirements.slice(0,4).map((r,i)=><div className="comparison-row" key={r.requirement}><div><p className="text-sm font-medium">{r.requirement}</p><p className="text-xs text-muted-foreground">{i === 3 && c.id === 2 ? "No specific scope stated" : r.evidence}</p></div><StatusBadge status={i === 3 && c.id === 2 ? "UNCERTAIN" : i === 4 ? "PARTIAL" : "MATCH"} /></div>)}</div></div>)}</div><CandidateDrawer candidate={drawer} open={!!drawer} onClose={() => setDrawer(null)} /></EvidenceDesk>;
}

export function InterviewKitPage({ roleId }: { roleId: string }) {
  return <EvidenceDesk roleId={roleId} active="Interview Kit"><div className="section-heading"><div><h2>Interview kit</h2><p>Evidence-linked questions for Candidate 017.</p></div><Button onClick={() => toast.success("Interview kit copied")}><FileSearch />Copy kit</Button></div><div className="space-y-3">{interviewQuestions.map((q,i)=><article className="question-card" key={q.question}><span className="question-number">{String(i+1).padStart(2,"0")}</span><div><EvidenceChip>{q.skill}</EvidenceChip><h3>{q.question}</h3><p>{q.reason}</p></div></article>)}</div><div className="decision-note"><ShieldCheck /><div><p className="font-semibold">Human decision required</p><p>RecruitRadar structures evidence and uncertainty. The recruiter makes every progression and hiring decision.</p></div></div></EvidenceDesk>;
}

export function SettingsPage() {
  const [blind, setBlind] = useState(true);
  return <AppShell><div className="page-wrap max-w-4xl"><div className="page-heading"><div><p className="eyebrow">Workspace</p><h1>Settings</h1><p>Control privacy and review defaults for your recruitment workspace.</p></div></div><section className="settings-section"><h2>Privacy & review</h2><div className="setting-row"><div><p className="font-medium">Blind Mode by default</p><p>Hide unnecessary identifying details in candidate lists.</p></div><Switch checked={blind} onCheckedChange={setBlind} /></div><div className="setting-row"><div><p className="font-medium">Uncertainty review</p><p>Keep uncertain evidence separate from missing requirements.</p></div><Switch checked disabled /></div></section><section className="settings-section"><h2>Scoring policy</h2><div className="policy-callout"><ShieldCheck /><div><p className="font-medium">Evidence-only scoring is enforced</p><p>Keyword presence has zero scoring weight across all roles.</p></div></div></section></div></AppShell>;
}