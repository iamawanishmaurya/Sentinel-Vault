"use client";
import { useEffect, useState } from "react";
import { Blocks, Box, Cpu, FileCode2, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Glass, Mono, PageHeader, StatusBadge, fmtDate } from "@/components/bits";
import { api } from "@/lib/api";

interface Info { chain_id: number; latest_block: number; contract_address: string; admin: string; document_count: number; client: string; issuers: { name: string; address: string; authorized: boolean }[] }
interface TxRow { tx_hash: string; kind: string; block_number: number; timestamp: string; from: string; from_name: string | null; to: string; doc_hash: string | null; document_title: string | null; gas_used: number; status: string }
interface Block { number: number; hash: string; timestamp: string; tx_count: number; gas_used: number }
interface TxDetail { tx_hash: string; block_number: number; block_hash: string; timestamp: string; from: string; to: string; nonce: number; gas_used: number; status: string; confirmations: number; events: { event: string; args: Record<string, unknown> }[] }

export default function Explorer() {
  const [info, setInfo] = useState<Info | null>(null);
  const [txs, setTxs] = useState<{ total: number; items: TxRow[] } | null>(null);
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [detail, setDetail] = useState<TxDetail | null>(null);
  const [q, setQ] = useState("");
  const load = () => {
    api<Info>("/chain/info").then(setInfo).catch((e) => toast.error(e.message));
    api<{ total: number; items: TxRow[] }>("/chain/transactions").then(setTxs);
    api<Block[]>("/chain/blocks?count=8").then(setBlocks).catch(() => {});
  };
  useEffect(() => { load(); const t = setInterval(load, 10000); return () => clearInterval(t); }, []);
  const open = (h: string) => api<TxDetail>(`/chain/tx/${h}`).then(setDetail).catch((e) => toast.error(e.message));
  return (
    <>
      <PageHeader title="Blockchain explorer" subtitle="Live view of the local Hardhat Ethereum network and the DocumentRegistry contract">
        <Button variant="outline" onClick={load}><RefreshCw className="size-4" />Refresh</Button>
      </PageHeader>
      {info && (
        <div className="grid gap-4 grid-cols-2 lg:grid-cols-4 mb-4">
          {[[Blocks, "Latest block", `#${info.latest_block}`], [Cpu, "Chain ID", info.chain_id], [FileCode2, "Documents on-chain", info.document_count], [Box, "Issuers", info.issuers.filter((i) => i.authorized).length]].map(([Icon, l, v]) => {
            const I = Icon as React.ElementType; return (
              <Glass key={String(l)} className="p-5"><div className="flex justify-between text-sm text-muted-foreground">{String(l)}<I className="size-4 text-cyan-300" /></div><div className="text-2xl font-semibold mt-2">{String(v)}</div></Glass>);
          })}
        </div>
      )}
      {info && <Glass className="p-5 mb-4 text-sm grid sm:grid-cols-[150px_1fr] gap-y-2">
        <span className="text-muted-foreground">Contract</span><Mono value={info.contract_address} short={false} />
        <span className="text-muted-foreground">Admin</span><Mono value={info.admin} short={false} />
        <span className="text-muted-foreground">Node</span><span className="font-mono text-xs">{info.client}</span>
        <span className="text-muted-foreground">Authorised issuers</span>
        <div className="space-y-1">{info.issuers.map((i) => <div key={i.address}>{i.name} <Mono value={i.address} /> <StatusBadge s={i.authorized ? "success" : "failed"} /></div>)}{!info.issuers.length && "—"}</div>
      </Glass>}
      <div className="grid lg:grid-cols-3 gap-4">
        <Glass className="p-4 lg:col-span-2">
          <div className="flex gap-2 mb-3"><h3 className="font-medium mr-auto self-center">Transactions {txs && <span className="text-muted-foreground text-sm">({txs.total})</span>}</h3>
            <Input className="w-72" placeholder="Look up tx hash…" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && q && open(q.trim())} /></div>
          <Table>
            <TableHeader><TableRow><TableHead>Tx hash</TableHead><TableHead>Type</TableHead><TableHead>Block</TableHead><TableHead>From (issuer)</TableHead><TableHead>Status</TableHead><TableHead>Time</TableHead></TableRow></TableHeader>
            <TableBody>
              {txs?.items.map((t) => (
                <TableRow key={t.tx_hash} className="cursor-pointer" onClick={() => open(t.tx_hash)}>
                  <TableCell><Mono value={t.tx_hash} /></TableCell><TableCell className="capitalize">{t.kind.replace("_", " ")}</TableCell><TableCell>#{t.block_number}</TableCell>
                  <TableCell><div className="text-xs">{t.from_name ?? "Admin / deployer"}</div><Mono value={t.from} /></TableCell><TableCell><StatusBadge s={t.status} /></TableCell>
                  <TableCell className="text-muted-foreground whitespace-normal">{fmtDate(t.timestamp)}</TableCell>
                </TableRow>
              ))}
              {!txs && <TableRow><TableCell colSpan={6} className="text-center py-10"><Loader2 className="size-5 animate-spin mx-auto" /></TableCell></TableRow>}
              {txs && !txs.items.length && <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground py-10">No transactions yet.</TableCell></TableRow>}
            </TableBody>
          </Table>
        </Glass>
        <Glass className="p-4">
          <h3 className="font-medium mb-3">Latest blocks</h3>
          <div className="space-y-2">{blocks.map((b) => (
            <div key={b.number} className="rounded-lg border border-white/10 px-3 py-2 text-sm flex justify-between items-center">
              <div><div className="font-medium text-cyan-200">#{b.number}</div><div className="text-xs text-muted-foreground">{fmtDate(b.timestamp)}</div></div>
              <div className="text-right text-xs text-muted-foreground">{b.tx_count} tx<br />{b.gas_used.toLocaleString()} gas</div>
            </div>))}</div>
        </Glass>
      </div>
      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="glass border-white/10 max-w-2xl">
          {detail && <>
            <DialogHeader><DialogTitle>Transaction details</DialogTitle></DialogHeader>
            <dl className="grid sm:grid-cols-[130px_1fr] gap-y-2 text-sm">
              <dt className="text-muted-foreground">Hash</dt><dd><Mono value={detail.tx_hash} short={false} /></dd>
              <dt className="text-muted-foreground">Status</dt><dd><StatusBadge s={detail.status} /> · {detail.confirmations} confirmation(s)</dd>
              <dt className="text-muted-foreground">Block</dt><dd>#{detail.block_number} <Mono value={detail.block_hash} /></dd>
              <dt className="text-muted-foreground">Timestamp</dt><dd>{fmtDate(detail.timestamp)}</dd>
              <dt className="text-muted-foreground">From</dt><dd><Mono value={detail.from} short={false} /></dd>
              <dt className="text-muted-foreground">To (contract)</dt><dd><Mono value={detail.to} short={false} /></dd>
              <dt className="text-muted-foreground">Gas used / nonce</dt><dd>{detail.gas_used.toLocaleString()} / {detail.nonce}</dd>
              <dt className="text-muted-foreground">Events</dt>
              <dd className="space-y-2">{detail.events.map((e, i) => <div key={i} className="rounded-md bg-black/30 p-2 font-mono text-xs"><b className="text-cyan-300">{e.event}</b>{Object.entries(e.args).map(([k, v]) => <div key={k} className="break-all text-slate-300">{k}: {String(v)}</div>)}</div>)}</dd>
            </dl></>}
        </DialogContent>
      </Dialog>
    </>
  );
}
