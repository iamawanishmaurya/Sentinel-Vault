"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Ban, Download, Link2, Loader2, Share2, ShieldPlus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Glass, FraudReportView, Mono, RiskBadge, StatusBadge, fmtDate, fmtSize } from "@/components/bits";
import { api, fetchBlob, type Doc } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function DocDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [d, setD] = useState<Doc | null>(null);
  const [email, setEmail] = useState("");
  const [days, setDays] = useState("7");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState("");
  const load = useCallback(() => { api<Doc>(`/documents/${id}`).then(setD).catch((e) => { toast.error(e.message); router.replace("/documents"); }); }, [id, router]);
  useEffect(load, [load]);
  if (!d) return <Loader2 className="size-6 animate-spin text-cyan-300" />;

  const act = async (name: string, fn: () => Promise<unknown>, ok: string) => {
    setBusy(name);
    try { await fn(); toast.success(ok); load(); } catch (e) { toast.error((e as Error).message); } finally { setBusy(""); }
  };
  const view = async (download: boolean) => {
    const b = await fetchBlob(`/documents/${d.id}/download`);
    const url = URL.createObjectURL(b);
    if (download) { const a = document.createElement("a"); a.href = url; a.download = d.filename; a.click(); } else window.open(url, "_blank");
  };
  const canIssue = user?.role === "issuer" && d.is_owner && d.status === "stored";
  const canRevoke = d.status === "registered" && (user?.role === "admin" || (user?.role === "issuer" && d.issuer));

  return (
    <>
      <Link href="/documents" className="text-sm text-muted-foreground hover:text-cyan-300 inline-flex items-center gap-1 mb-4"><ArrowLeft className="size-4" />Documents</Link>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
        <div><h1 className="text-2xl font-semibold">{d.title}</h1><div className="text-sm text-muted-foreground">{d.filename} · {fmtSize(d.size_bytes)} · uploaded {fmtDate(d.created_at)}</div></div>
        <div className="flex gap-2 items-center"><StatusBadge s={d.status} /><RiskBadge level={d.fraud_report?.risk_level} /></div>
      </div>
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <Glass className="p-5 space-y-3">
            <h3 className="font-medium">Integrity</h3>
            <dl className="grid sm:grid-cols-[140px_1fr] gap-y-2 text-sm">
              <dt className="text-muted-foreground">SHA-256</dt><dd><Mono value={d.sha256} short={false} /></dd>
              <dt className="text-muted-foreground">Encryption</dt><dd>AES-256-GCM, per-file random key (envelope encrypted)</dd>
              <dt className="text-muted-foreground">Owner</dt><dd>{d.owner.name}</dd>
              <dt className="text-muted-foreground">Issuer</dt><dd>{d.issuer ? <>{d.issuer.name} <Mono value={d.issuer.address} /></> : "—"}</dd>
              <dt className="text-muted-foreground">IPFS CID</dt><dd><Mono value={d.ipfs_cid} /></dd>
            </dl>
            <div className="flex flex-wrap gap-2 pt-2">
              <Button variant="outline" onClick={() => view(false)}>View</Button>
              <Button variant="outline" onClick={() => view(true)}><Download className="size-4" />Download (decrypted)</Button>
              {canIssue && <Button disabled={!!busy} onClick={() => act("reg", () => api(`/documents/${d.id}/register`, { method: "POST" }), "Registered on blockchain")}>{busy === "reg" ? <Loader2 className="size-4 animate-spin" /> : <ShieldPlus className="size-4" />}Register on blockchain</Button>}
              {d.is_owner && d.status === "stored" && <Button variant="destructive" onClick={() => confirm("Delete this document?") && act("del", async () => { await api(`/documents/${d.id}`, { method: "DELETE" }); router.replace("/documents"); }, "Deleted")}><Trash2 className="size-4" />Delete</Button>}
            </div>
          </Glass>

          <Glass className="p-5">
            <h3 className="font-medium mb-3 flex items-center gap-2"><Link2 className="size-4 text-cyan-300" />Blockchain transactions</h3>
            {d.transactions?.length ? d.transactions.map((t) => (
              <div key={t.tx_hash} className="flex flex-wrap items-center justify-between gap-2 py-2 border-b border-white/5 last:border-0 text-sm">
                <div><span className="capitalize font-medium">{t.kind}</span> <span className="text-muted-foreground">· block #{t.block_number} · {fmtDate(t.timestamp)}</span></div>
                <div className="flex items-center gap-2"><Mono value={t.tx_hash} /><StatusBadge s={t.status} /></div>
              </div>
            )) : <p className="text-sm text-muted-foreground">Not registered on-chain yet.</p>}
            {canRevoke && (
              <div className="flex gap-2 mt-4"><Input placeholder="Revocation reason" value={reason} onChange={(e) => setReason(e.target.value)} />
                <Button variant="destructive" disabled={reason.length < 3 || !!busy} onClick={() => act("rev", () => api(`/documents/${d.id}/revoke`, { json: { reason } }), "Revoked on-chain")}><Ban className="size-4" />Revoke</Button></div>
            )}
          </Glass>

          {d.fraud_report && <Glass className="p-5"><h3 className="font-medium mb-3">Fraud analytics report</h3><FraudReportView r={d.fraud_report} /></Glass>}
        </div>

        <div>
          {d.shares && (
            <Glass className="p-5">
              <h3 className="font-medium mb-3 flex items-center gap-2"><Share2 className="size-4 text-cyan-300" />Secure sharing</h3>
              <div className="space-y-2 mb-4">
                <Input placeholder="Recipient email (registered user)" value={email} onChange={(e) => setEmail(e.target.value)} />
                <div className="flex gap-2"><Input type="number" min={1} max={365} value={days} onChange={(e) => setDays(e.target.value)} className="w-24" /><span className="text-sm self-center text-muted-foreground">days</span>
                  <Button className="ml-auto" disabled={!email || !!busy} onClick={() => act("share", () => api(`/documents/${d.id}/share`, { json: { email, expires_days: Number(days) } }), "Shared").then(() => setEmail(""))}>Share</Button></div>
              </div>
              {d.shares.map((s) => (
                <div key={s.id} className="flex items-center justify-between text-sm py-2 border-t border-white/5">
                  <div><div>{s.user.name}</div><div className="text-xs text-muted-foreground">{s.user.email} · expires {s.expires_at ? fmtDate(s.expires_at) : "never"}</div></div>
                  <Button size="sm" variant="ghost" onClick={() => act("unshare", () => api(`/documents/${d.id}/share/${s.id}`, { method: "DELETE" }), "Access removed")}>Remove</Button>
                </div>
              ))}
              {!d.shares.length && <p className="text-sm text-muted-foreground">Not shared with anyone.</p>}
            </Glass>
          )}
        </div>
      </div>
    </>
  );
}
