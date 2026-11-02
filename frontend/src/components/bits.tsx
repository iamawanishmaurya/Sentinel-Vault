"use client";
import { AlertTriangle, CheckCircle2, CircleHelp, Copy, FileWarning, ShieldAlert, ShieldCheck, ShieldX } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { FraudReport, VStatus } from "@/lib/api";

export const STATUS_STYLE: Record<string, string> = {
  Verified: "bg-emerald-500/15 text-emerald-300 border-emerald-400/30",
  Modified: "bg-amber-500/15 text-amber-300 border-amber-400/30",
  Unknown: "bg-slate-500/20 text-slate-300 border-slate-400/30",
  Revoked: "bg-rose-500/15 text-rose-300 border-rose-400/30",
  registered: "bg-emerald-500/15 text-emerald-300 border-emerald-400/30",
  stored: "bg-sky-500/15 text-sky-300 border-sky-400/30",
  revoked: "bg-rose-500/15 text-rose-300 border-rose-400/30",
  success: "bg-emerald-500/15 text-emerald-300 border-emerald-400/30",
  failed: "bg-rose-500/15 text-rose-300 border-rose-400/30",
};
export const RISK_STYLE: Record<string, string> = {
  Low: "bg-emerald-500/15 text-emerald-300 border-emerald-400/30",
  Medium: "bg-amber-500/15 text-amber-300 border-amber-400/30",
  High: "bg-rose-500/15 text-rose-300 border-rose-400/30",
};

export function StatusBadge({ s }: { s: string }) {
  return <Badge variant="outline" className={cn("capitalize", STATUS_STYLE[s])}>{s}</Badge>;
}
export function RiskBadge({ level }: { level?: string | null }) {
  if (!level) return <span className="text-muted-foreground text-xs">—</span>;
  return <Badge variant="outline" className={RISK_STYLE[level]}>{level} risk</Badge>;
}

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>}
      </div>
      <div className="flex gap-2">{children}</div>
    </div>
  );
}

export function Glass({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("glass rounded-2xl", className)}>{children}</div>;
}

export function Mono({ value, short = true, className }: { value?: string | null; short?: boolean; className?: string }) {
  if (!value) return <span className="text-muted-foreground">—</span>;
  const text = short && value.length > 20 ? `${value.slice(0, 10)}…${value.slice(-8)}` : value;
  return (
    <button type="button" title="Click to copy" onClick={() => { navigator.clipboard.writeText(value); toast.success("Copied"); }}
      className={cn("font-mono text-xs text-cyan-200/90 hover:text-cyan-100 inline-flex items-center gap-1 break-all text-left", className)}>
      {text}<Copy className="size-3 shrink-0 opacity-50" />
    </button>
  );
}

export const fmtDate = (s?: string | null) => (s ? new Date(s).toLocaleString() : "—");
export const fmtSize = (n: number) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);

export const VERDICT: Record<VStatus, { icon: React.ElementType; color: string; title: string; blurb: string }> = {
  Verified: { icon: ShieldCheck, color: "text-emerald-300", title: "Verified", blurb: "Hash matches an on-chain record issued by an authorised issuer." },
  Modified: { icon: FileWarning, color: "text-amber-300", title: "Modified", blurb: "This file does not match the registered fingerprint but resembles a registered document." },
  Unknown: { icon: CircleHelp, color: "text-slate-300", title: "Unknown", blurb: "No trustworthy blockchain record exists for this file." },
  Revoked: { icon: ShieldX, color: "text-rose-300", title: "Revoked", blurb: "The issuer revoked this document on-chain." },
};

export function ScoreBar({ label, value }: { label: string; value: number | null | undefined }) {
  if (value == null) return null;
  const color = value >= 0.65 ? "bg-rose-400" : value >= 0.35 ? "bg-amber-400" : "bg-emerald-400";
  return (
    <div>
      <div className="flex justify-between text-xs text-muted-foreground mb-1"><span>{label}</span><span>{(value * 100).toFixed(0)}%</span></div>
      <div className="h-1.5 rounded-full bg-white/10 overflow-hidden"><div className={cn("h-full rounded-full transition-all duration-700", color)} style={{ width: `${Math.max(2, value * 100)}%` }} /></div>
    </div>
  );
}

export function FraudReportView({ r }: { r: FraudReport }) {
  const Icon = r.risk_level === "High" ? ShieldAlert : r.risk_level === "Medium" ? AlertTriangle : CheckCircle2;
  const comps = (r.features?.components ?? null) as Record<string, number> | null;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Icon className={cn("size-8", r.risk_level === "High" ? "text-rose-400" : r.risk_level === "Medium" ? "text-amber-400" : "text-emerald-400")} />
        <div>
          <div className="text-lg font-semibold">{r.risk_level} risk <span className="text-muted-foreground font-normal text-sm">· score {(r.risk_score * 100).toFixed(0)}/100</span></div>
          <div className="text-xs text-muted-foreground">Final score = highest component (transparent max rule)</div>
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <ScoreBar label="Random Forest · tampering probability" value={r.document_score} />
        <ScoreBar label="Isolation Forest · activity anomaly" value={r.activity_score} />
        {comps && Object.entries(comps).filter(([k]) => !["document_model", "activity_model"].includes(k)).map(([k, v]) => <ScoreBar key={k} label={k.replace(/_/g, " ")} value={v} />)}
      </div>
      <div>
        <div className="text-sm font-medium mb-2">Why this was flagged</div>
        <ul className="space-y-1.5">
          {r.reasons.map((x, i) => (
            <li key={i} className="text-sm flex gap-2">
              <Badge variant="outline" className="shrink-0 text-[10px] h-5 border-cyan-400/30 text-cyan-300">{x.source.replace("_", " ")}</Badge>
              <span className="text-slate-200">{x.text}</span>
            </li>
          ))}
        </ul>
      </div>
      <p className="text-[11px] text-amber-300/80 border border-amber-400/20 rounded-lg px-3 py-2 bg-amber-500/5">
        Models are trained on <b>synthetic</b> data (simulated certificates & activity) for demonstration. Treat scores as decision support, not proof.
      </p>
    </div>
  );
}
