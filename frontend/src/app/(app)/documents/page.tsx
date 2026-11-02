"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { FileUp, Loader2, Search, Upload } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Glass, Mono, PageHeader, RiskBadge, StatusBadge, fmtDate, fmtSize } from "@/components/bits";
import { api, type Doc } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function UploadDialog({ onDone }: { onDone: () => void }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [type, setType] = useState("certificate");
  const [reg, setReg] = useState(user?.role === "issuer");
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  async function submit() {
    if (!file) return;
    setBusy(true);
    const fd = new FormData();
    fd.append("file", file); fd.append("title", title); fd.append("doc_type", type); fd.append("register_on_chain", String(reg));
    try {
      const d = await api<Doc>("/documents", { form: fd });
      toast.success(d.status === "registered" ? "Encrypted, hashed and registered on-chain" : "Encrypted and stored");
      setOpen(false); setFile(null); setTitle(""); onDone();
    } catch (e) { toast.error((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button />}><Upload className="size-4" />Upload document</DialogTrigger>
      <DialogContent className="glass border-white/10">
        <DialogHeader><DialogTitle>Upload document</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) { setFile(f); if (!title) setTitle(f.name.replace(/\.[^.]+$/, "")); } }}
            onClick={() => input.current?.click()}
            className={`cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-colors ${drag ? "border-cyan-400 bg-cyan-400/10" : "border-white/15 hover:border-cyan-400/50"}`}>
            <FileUp className="size-8 mx-auto text-cyan-300 mb-2" />
            <div className="text-sm">{file ? <b>{file.name}</b> : "Drop a PDF, JPG or PNG here, or click to browse"}</div>
            <input ref={input} type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" hidden
              onChange={(e) => { const f = e.target.files?.[0]; if (f) { setFile(f); if (!title) setTitle(f.name.replace(/\.[^.]+$/, "")); } }} />
          </div>
          <div className="space-y-2"><Label>Title</Label><Input value={title} onChange={(e) => setTitle(e.target.value)} /></div>
          <div className="space-y-2"><Label>Type</Label>
            <Select value={type} onValueChange={(v) => v && setType(v)}><SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{["certificate", "transcript", "identity", "contract", "other"].map((t) => <SelectItem key={t} value={t} className="capitalize">{t}</SelectItem>)}</SelectContent></Select></div>
          {user?.role === "issuer" && (
            <div className="flex items-center justify-between rounded-lg border border-white/10 p-3">
              <div><div className="text-sm font-medium">Register on blockchain</div><div className="text-xs text-muted-foreground">Official document signed by your issuer wallet</div></div>
              <Switch checked={reg} onCheckedChange={setReg} />
            </div>
          )}
          <Button className="w-full" disabled={!file || busy} onClick={submit}>{busy && <Loader2 className="size-4 animate-spin" />}Encrypt & upload</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function Documents() {
  const { user } = useAuth();
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");
  const load = useCallback(() => {
    const p = new URLSearchParams(); if (q) p.set("q", q); if (status !== "all") p.set("status", status);
    api<Doc[]>(`/documents?${p}`).then(setDocs).catch((e) => toast.error(e.message));
  }, [q, status]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);
  return (
    <>
      <PageHeader title="Documents" subtitle="Encrypted at rest with AES-256-GCM · SHA-256 fingerprinted"><UploadDialog onDone={load} /></PageHeader>
      <Glass className="p-4">
        <div className="flex flex-wrap gap-3 mb-4">
          <div className="relative flex-1 min-w-56"><Search className="size-4 absolute left-3 top-2.5 text-muted-foreground" /><Input className="pl-9" placeholder="Search title, filename or hash…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <Select value={status} onValueChange={(v) => v && setStatus(v)}><SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All statuses</SelectItem><SelectItem value="stored">Stored</SelectItem><SelectItem value="registered">Registered</SelectItem><SelectItem value="revoked">Revoked</SelectItem></SelectContent></Select>
        </div>
        <Table>
          <TableHeader><TableRow><TableHead>Title</TableHead><TableHead>Status</TableHead><TableHead>SHA-256</TableHead><TableHead>Risk</TableHead><TableHead>Size</TableHead><TableHead>Owner</TableHead><TableHead>Uploaded</TableHead></TableRow></TableHeader>
          <TableBody>
            {docs?.map((d) => (
              <TableRow key={d.id} className="cursor-pointer">
                <TableCell><Link href={`/documents/${d.id}`} className="font-medium hover:text-cyan-300">{d.title}</Link><div className="text-xs text-muted-foreground">{d.filename}</div></TableCell>
                <TableCell><StatusBadge s={d.status} /></TableCell><TableCell><Mono value={d.sha256} /></TableCell>
                <TableCell><RiskBadge level={d.risk_level} /></TableCell><TableCell className="text-muted-foreground">{fmtSize(d.size_bytes)}</TableCell>
                <TableCell className="text-muted-foreground">{d.owner.id === user?.id ? "You" : d.owner.name}</TableCell><TableCell className="text-muted-foreground">{fmtDate(d.created_at)}</TableCell>
              </TableRow>
            ))}
            {docs && !docs.length && <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground py-10">No documents yet. Upload your first one.</TableCell></TableRow>}
            {!docs && <TableRow><TableCell colSpan={7} className="text-center py-10"><Loader2 className="size-5 animate-spin mx-auto" /></TableCell></TableRow>}
          </TableBody>
        </Table>
      </Glass>
    </>
  );
}
