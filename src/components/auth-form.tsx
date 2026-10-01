import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowRight, CheckCircle2, Eye, EyeOff } from "lucide-react";
import { Brand } from "@/components/recruitradar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { lovable } from "@/integrations/lovable";
import { supabase } from "@/integrations/supabase/client";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const navigate = useNavigate();
  const [name, setName] = useState(""); const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [success, setSuccess] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError("");
    if (mode === "signup" && password !== confirm) { setError("Passwords do not match."); return; }
    if (password.length < 8) { setError("Use at least 8 characters for your password."); return; }
    setBusy(true);
    if (mode === "signup") {
      const { data, error: authError } = await supabase.auth.signUp({ email, password, options: { emailRedirectTo: window.location.origin, data: { display_name: name } } });
      if (authError) setError(authError.message); else if (data.session && data.user) { await supabase.from("profiles").upsert({ id: data.user.id, display_name: name }); navigate({ to: "/roles" }); } else setSuccess(true);
    } else {
      const { data, error: authError } = await supabase.auth.signInWithPassword({ email, password });
      if (authError) setError(authError.message); else if (data.user) { await supabase.from("profiles").upsert({ id: data.user.id, display_name: data.user.user_metadata["display_name"] ?? "Recruiter" }); navigate({ to: "/roles" }); }
    }
    setBusy(false);
  }
  async function google() {
    setBusy(true); setError("");
    const result = await lovable.auth.signInWithOAuth("google", { redirect_uri: window.location.origin });
    if (result.error) { setError(result.error.message); setBusy(false); return; }
    if (!result.redirected) navigate({ to: "/roles" });
  }
  if (success) return <AuthFrame><div className="auth-success"><CheckCircle2 /><h1>Check your inbox</h1><p>We sent a confirmation link to <strong>{email}</strong>. Confirm your email to enter your workspace.</p><Button variant="outline" asChild><Link to="/login">Back to sign in</Link></Button></div></AuthFrame>;
  return <AuthFrame><div className="mb-8"><p className="eyebrow">Recruitment intelligence</p><h1>{mode === "login" ? "Welcome back" : "Create your workspace"}</h1><p>{mode === "login" ? "Sign in to continue reviewing evidence." : "Start building explainable, evidence-backed shortlists."}</p></div><Button variant="outline" className="w-full" onClick={google} disabled={busy}><span className="google-mark">G</span>Continue with Google</Button><div className="auth-divider"><span>or continue with email</span></div><form className="space-y-4" onSubmit={submit}>{mode === "signup" && <div><Label htmlFor="name">Name</Label><Input id="name" value={name} onChange={(e) => setName(e.target.value)} required className="mt-2" autoComplete="name" /></div>}<div><Label htmlFor="email">Email</Label><Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="mt-2" autoComplete="email" /></div><div><div className="flex items-center justify-between"><Label htmlFor="password">Password</Label>{mode === "login" && <Link to="/forgot-password" className="text-xs font-medium text-primary">Forgot password?</Link>}</div><div className="relative mt-2"><Input id="password" type={show ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete={mode === "login" ? "current-password" : "new-password"} className="pr-10" /><button type="button" className="password-toggle" onClick={() => setShow(!show)} aria-label={show ? "Hide password" : "Show password"}>{show ? <EyeOff /> : <Eye />}</button></div></div>{mode === "signup" && <div><Label htmlFor="confirm">Confirm password</Label><Input id="confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required className="mt-2" autoComplete="new-password" /></div>}{error && <p role="alert" className="auth-error">{error}</p>}<Button className="w-full" type="submit" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}<ArrowRight /></Button></form><p className="mt-6 text-center text-sm text-muted-foreground">{mode === "login" ? "New to RecruitRadar?" : "Already have an account?"} <Link className="font-semibold text-primary" to={mode === "login" ? "/signup" : "/login"}>{mode === "login" ? "Create account" : "Sign in"}</Link></p></AuthFrame>;
}

function AuthFrame({ children }: { children: React.ReactNode }) { return <main className="auth-page"><Link to="/" className="auth-brand"><Brand /></Link><section className="auth-panel">{children}</section><p className="auth-foot">Evidence over keywords. Human decisions remain final.</p></main>; }