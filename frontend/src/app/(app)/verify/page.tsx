"use client";
import { useRef, useState } from "react";
import { FileSearch, Loader2, ScanLine } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FraudReportView, Glass, Mono, PageHeader, VERDICT, fmtDate } from "@/components/bits";
import { api, type Verification } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function VerifyPage() {
  const [file, setFile] = useState<File | null>(null);
  const [claimed, setClaimed] = useState("");
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [res, setRes] = useState<Verification | null>(null);
  const input = useRef<HTMLInputElement>(null);
  async function run() {
    if (!file) return;
    setBusy(true); setRes(null);
    const fd = new FormData(); fd.append("file", file); if (claimed) fd.append("claimed_document_id", claimed);
    try { setRes(await api<Verification>("/verify", { form: fd })); } catch (e) { toast.error((e as Error).message); } finally { setBusy(false); }
  }
  const V = res && VERDICT[res.status];
  const ring = { Verified: "border-emerald-400/40 shadow-[0_0_40px_rgba(52,211,153,.15)]", Modified: "border-amber-400/40 shadow-[0_0_40px_rgba(245,158,11,.15)]", Unknown: "border-slate-400/30", Revoked: "border-rose-400/40 shadow-[0_0_40px_rgba(244,63,94,.15)]" };
  return (
    <>
      <PageHeader title="Verify a document" subtitle="We hash your file, query the Ethereum registry, check issuer authority and run fraud analytics" />
      <div className="grid lg:grid-cols-5 gap-4">
        <Glass className="p-5 lg:col-span-2 space-y-4 self-start">
          <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); setFile(e.dataTransfer.files[0] ?? null); }} onClick={() => input.current?.click()}
            className={cn("relative overflow-hidden cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-colors", drag ? "border-cyan-400 bg-cyan-400/10" : "border-white/15 hover:border-cyan-400/50")}>
            {busy && <div className="absolute inset-x-0 h-20 bg-gradient-to-b from-transparent via-cyan-400/25 to-transparent scanline" />}
            <ScanLine className="size-9 mx-auto text-cyan-300 mb-3" />
            <div className="text-sm">{file ? <><b>{file.name}</b><div className="text-xs text-muted-foreground mt-1">{(file.size / 1024).toFixed(0)} KB</div></> : "Drop the document to verify (PDF, JPG, PNG)"}</div>
            <input ref={input} type="file" hidden accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </div>
          <div className="space-y-2"><Label>Claimed document ID <span className="text-muted-foreground">(optional)</span></Label>
            <Input type="number" placeholder="If you know which record this should match" value={claimed} onChange={(e) => setClaimed(e.target.value)} /></div>
          <Button className="w-full" size="lg" disabled={!file || busy} onClick={run}>{busy ? <Loader2 className="size-4 animate-spin" /> : <FileSearch className="size-4" />}Verify against blockchain</Button>
        </Glass>

        <div className="lg:col-span-3 space-y-4">
          {!res && !busy && <Glass className="p-10 text-center text-muted-foreground text-sm">Results appear here: <b className="text-slate-200">Verified</b>, <b className="text-slate-200">Modified</b>, <b className="text-slate-200">Unknown</b> or <b className="text-slate-200">Revoked</b>.</Glass>}
          {res && V && (
            <>
              <Glass className={cn("p-6 border animate-in fade-in zoom-in-95 duration-500", ring[res.status])}>
                <div className="flex items-center gap-4">
                  <V.icon className={cn("size-14", V.color)} />
                  <div><div className={cn("text-3xl font-semibold", V.color)}>{V.title}</div><div className="text-sm text-slate-300">{V.blurb}</div></div>
                </div>
                <dl className="grid sm:grid-cols-[150px_1fr] gap-y-2 text-sm mt-5">
                  <dt className="text-muted-foreground">Submitted SHA-256</dt><dd><Mono value={res.file_sha256} short={false} /></dd>
                  {res.details.registered_hash && <><dt className="text-muted-foreground">Registered SHA-256</dt><dd><Mono value={res.details.registered_hash} short={false} /></dd></>}
                  {res.details.document_title && <><dt className="text-muted-foreground">Matched record</dt><dd>{res.details.document_title}</dd></>}
                  <dt className="text-muted-foreground">Issuer</dt><dd>{res.details.issuer_name ?? "—"} <Mono value={res.issuer_address} /></dd>
                  <dt className="text-muted-foreground">Issuer authorised</dt><dd>{res.issuer_authorized == null ? "—" : res.issuer_authorized ? "Yes" : "No"}</dd>
                  <dt className="text-muted-foreground">Registered on-chain</dt><dd>{fmtDate(res.chain_timestamp)}</dd>
                  {res.similarity != null && <><dt className="text-muted-foreground">Content similarity</dt><dd>{(res.similarity * 100).toFixed(0)}%</dd></>}
                </dl>
                <ul className="mt-4 space-y-1 text-sm text-slate-300 list-disc pl-5">{res.details.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
              </Glass>
              {res.fraud_report && <Glass className="p-6"><h3 className="font-medium mb-4">Fraud analytics report</h3><FraudReportView r={res.fraud_report} /></Glass>}
            </>
          )}
        </div>
      </div>
    </>
  );
}
