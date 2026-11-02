"use client";
import { useEffect, useState } from "react";
import { Brain, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Glass, PageHeader, RiskBadge, StatusBadge, fmtDate, ScoreBar } from "@/components/bits";
import { api, type Reason } from "@/lib/api";

interface Report {
  id: number; subject_type: string; risk_level: "Low" | "Medium" | "High"; risk_score: number; document_score: number | null; activity_score: number | null;
  reasons: Reason[]; created_at: string; document_title: string | null; verification_status: string | null; filename: string | null; components: Record<string, number> | null;
}
interface Card { notice: string; trained_at: string; document_model: { type: string; samples: number; holdout_roc_auc: number; cv5_roc_auc: number; features: string[] }; activity_model: { type: string; samples: number; features: string[] } }

export default function Analytics() {
  const [level, setLevel] = useState("all");
  const [rows, setRows] = useState<Report[] | null>(null);
  const [card, setCard] = useState<Card | null>(null);
  const [sel, setSel] = useState<Report | null>(null);
  useEffect(() => { api<Card>("/analytics/model-card").then(setCard); }, []);
  useEffect(() => { setRows(null); api<Report[]>(`/analytics/reports${level !== "all" ? `?level=${level}` : ""}`).then(setRows); }, [level]);
  return (
    <>
      <PageHeader title="Fraud analytics" subtitle="Random Forest document forensics · Isolation Forest activity anomaly detection · transparent rules" />
      {card && (
        <Glass className="p-5 mb-4">
          <div className="flex items-center gap-2 mb-3"><Brain className="size-5 text-cyan-300" /><h3 className="font-medium">Model card</h3><Badge variant="outline" className="border-amber-400/40 text-amber-300">Synthetic training data</Badge></div>
          <p className="text-sm text-muted-foreground mb-3">{card.notice}</p>
          <div className="grid sm:grid-cols-2 gap-4 text-sm">
            <div><div className="font-medium">Document forensics · {card.document_model.type}</div><div className="text-muted-foreground">{card.document_model.samples} synthetic certificates · holdout ROC-AUC {card.document_model.holdout_roc_auc} · 5-fold CV {card.document_model.cv5_roc_auc}</div>
              <div className="text-xs text-muted-foreground mt-1">Features: ELA, noise & sharpness consistency, OCR confidence & text-height statistics, file metadata</div></div>
            <div><div className="font-medium">Activity · {card.activity_model.type}</div><div className="text-muted-foreground">{card.activity_model.samples} synthetic normal activity windows</div>
              <div className="text-xs text-muted-foreground mt-1">Features: request bursts, distinct documents, failure ratio, time of day, new IP</div></div>
          </div>
        </Glass>
      )}
      <Glass className="p-4">
        <div className="flex items-center justify-between mb-3"><h3 className="font-medium">Risk reports</h3>
          <Tabs value={level} onValueChange={setLevel}><TabsList>{["all", "High", "Medium", "Low"].map((l) => <TabsTrigger key={l} value={l} className="capitalize">{l}</TabsTrigger>)}</TabsList></Tabs></div>
        <Table>
          <TableHeader><TableRow><TableHead>Subject</TableHead><TableHead>Type</TableHead><TableHead>Result</TableHead><TableHead>Risk</TableHead><TableHead>Score</TableHead><TableHead>Top reason</TableHead><TableHead>When</TableHead></TableRow></TableHeader>
          <TableBody>
            {rows?.map((r) => (
              <TableRow key={r.id} className="cursor-pointer" onClick={() => setSel(r)}>
                <TableCell className="font-medium max-w-48 truncate">{r.document_title ?? r.filename ?? "—"}</TableCell>
                <TableCell className="capitalize text-muted-foreground">{r.subject_type}</TableCell>
                <TableCell>{r.verification_status ? <StatusBadge s={r.verification_status} /> : <span className="text-muted-foreground">—</span>}</TableCell>
                <TableCell><RiskBadge level={r.risk_level} /></TableCell><TableCell className="tabular-nums">{(r.risk_score * 100).toFixed(0)}</TableCell>
                <TableCell className="text-muted-foreground max-w-72 truncate">{r.reasons[0]?.text}</TableCell><TableCell className="text-muted-foreground">{fmtDate(r.created_at)}</TableCell>
              </TableRow>
            ))}
            {!rows && <TableRow><TableCell colSpan={7} className="text-center py-10"><Loader2 className="size-5 animate-spin mx-auto" /></TableCell></TableRow>}
            {rows && !rows.length && <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground py-10">No reports match.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </Glass>
      <Dialog open={!!sel} onOpenChange={(o) => !o && setSel(null)}>
        <DialogContent className="glass border-white/10 max-w-xl">
          {sel && <>
            <DialogHeader><DialogTitle className="flex items-center gap-2">{sel.document_title ?? sel.filename}<RiskBadge level={sel.risk_level} /></DialogTitle></DialogHeader>
            <div className="space-y-3">
              <ScoreBar label="Final risk score" value={sel.risk_score} /><ScoreBar label="Random Forest" value={sel.document_score} /><ScoreBar label="Isolation Forest" value={sel.activity_score} />
              <ul className="space-y-1.5 pt-2">{sel.reasons.map((x, i) => <li key={i} className="text-sm flex gap-2"><Badge variant="outline" className="shrink-0 text-[10px] h-5 border-cyan-400/30 text-cyan-300">{x.source.replace("_", " ")}</Badge>{x.text}</li>)}</ul>
            </div>
          </>}
        </DialogContent>
      </Dialog>
    </>
  );
}
