"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, Ban, Boxes, FileCheck2, FileText, FileWarning, ShieldCheck } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Glass, PageHeader, RiskBadge, StatusBadge, fmtDate } from "@/components/bits";
import { api, type Verification } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Dash {
  totals: Record<string, number>;
  risk_distribution: Record<string, number>;
  verification_timeline: Record<string, string | number>[];
  risk_timeline: Record<string, string | number>[];
  recent_verifications: Verification[];
}
const tip = { contentStyle: { background: "#0b1630", border: "1px solid rgba(120,160,255,.25)", borderRadius: 10, fontSize: 12 } };
const axis = { stroke: "#8ea0bf", fontSize: 11, tickLine: false, axisLine: false } as const;
const day = (d: string) => d.slice(5);

export default function Dashboard() {
  const [d, setD] = useState<Dash | null>(null);
  useEffect(() => { api<Dash>("/dashboard").then(setD); }, []);
  if (!d) return <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}</div>;
  const t = d.totals;
  const cards = [
    { label: "Total documents", v: t.documents, icon: FileText, c: "text-cyan-300" },
    { label: "Verified", v: t.verified, icon: ShieldCheck, c: "text-emerald-300" },
    { label: "Modified", v: t.modified, icon: FileWarning, c: "text-amber-300" },
    { label: "Revoked", v: t.revoked, icon: Ban, c: "text-rose-300", sub: `${t.revoked_documents} revoked document(s)` },
    { label: "Blockchain transactions", v: t.blockchain_transactions, icon: Boxes, c: "text-blue-300" },
    { label: "Suspicious activities", v: t.suspicious_activities, icon: AlertTriangle, c: "text-orange-300", sub: "Medium/High risk verifications" },
    { label: "Unknown results", v: t.unknown, icon: FileCheck2, c: "text-slate-300" },
    { label: "Total verifications", v: t.verifications, icon: ShieldCheck, c: "text-cyan-300" },
  ];
  const pie = Object.entries(d.risk_distribution).map(([name, value]) => ({ name, value }));
  const PIE = { Low: "#34d399", Medium: "#f59e0b", High: "#f43f5e" } as Record<string, string>;
  return (
    <>
      <PageHeader title="Security overview" subtitle="Live data from the vault, the verification engine and the Ethereum node" />
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        {cards.map(({ label, v, icon: Icon, c, sub }, i) => (
          <Glass key={label} className="p-5 animate-in fade-in slide-in-from-bottom-3 duration-500" >
            <div className="flex items-center justify-between"><span className="text-sm text-muted-foreground">{label}</span><Icon className={cn("size-4", c)} /></div>
            <div className="text-3xl font-semibold mt-2 tabular-nums">{v}</div>
            {sub && <div className="text-[11px] text-muted-foreground mt-1">{sub}</div>}
          </Glass>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3 mt-4">
        <Glass className="p-5 lg:col-span-2">
          <h3 className="font-medium mb-4">Verification results · last 14 days</h3>
          <div className="h-64"><ResponsiveContainer>
            <BarChart data={d.verification_timeline}><CartesianGrid stroke="rgba(120,160,255,.08)" vertical={false} />
              <XAxis dataKey="date" tickFormatter={day} {...axis} /><YAxis allowDecimals={false} {...axis} /><Tooltip {...tip} cursor={{ fill: "rgba(255,255,255,.04)" }} /><Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="Verified" stackId="a" fill="#34d399" /><Bar dataKey="Modified" stackId="a" fill="#f59e0b" /><Bar dataKey="Unknown" stackId="a" fill="#64748b" /><Bar dataKey="Revoked" stackId="a" fill="#f43f5e" radius={[4, 4, 0, 0]} />
            </BarChart></ResponsiveContainer></div>
        </Glass>
        <Glass className="p-5">
          <h3 className="font-medium mb-4">Risk distribution</h3>
          <div className="h-64"><ResponsiveContainer>
            <PieChart><Pie data={pie} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={3} stroke="none">
              {pie.map((p) => <Cell key={p.name} fill={PIE[p.name]} />)}</Pie><Tooltip {...tip} /><Legend wrapperStyle={{ fontSize: 12 }} /></PieChart></ResponsiveContainer></div>
        </Glass>
      </div>

      <Glass className="p-5 mt-4">
        <h3 className="font-medium mb-4">Fraud risk reports over time</h3>
        <div className="h-52"><ResponsiveContainer>
          <AreaChart data={d.risk_timeline}><CartesianGrid stroke="rgba(120,160,255,.08)" vertical={false} /><XAxis dataKey="date" tickFormatter={day} {...axis} /><YAxis allowDecimals={false} {...axis} /><Tooltip {...tip} />
            <Area dataKey="Low" stackId="1" stroke="#34d399" fill="#34d39933" /><Area dataKey="Medium" stackId="1" stroke="#f59e0b" fill="#f59e0b33" /><Area dataKey="High" stackId="1" stroke="#f43f5e" fill="#f43f5e33" /></AreaChart></ResponsiveContainer></div>
      </Glass>

      <Glass className="p-5 mt-4">
        <div className="flex items-center justify-between mb-3"><h3 className="font-medium">Recent verification history</h3><Link href="/verify" className="text-xs text-cyan-300 hover:underline">Verify a document →</Link></div>
        <Table>
          <TableHeader><TableRow><TableHead>File</TableHead><TableHead>Result</TableHead><TableHead>Risk</TableHead><TableHead>Issuer</TableHead><TableHead>By</TableHead><TableHead>When</TableHead></TableRow></TableHeader>
          <TableBody>
            {d.recent_verifications.map((v) => (
              <TableRow key={v.id}>
                <TableCell className="font-medium max-w-48 truncate">{v.filename}</TableCell><TableCell><StatusBadge s={v.status} /></TableCell>
                <TableCell><RiskBadge level={v.fraud_report?.risk_level} /></TableCell><TableCell className="text-muted-foreground">{v.details?.issuer_name ?? "—"}</TableCell>
                <TableCell className="text-muted-foreground">{v.verifier.name}</TableCell><TableCell className="text-muted-foreground">{fmtDate(v.created_at)}</TableCell>
              </TableRow>
            ))}
            {!d.recent_verifications.length && <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground py-8">No verifications yet.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </Glass>
    </>
  );
}
