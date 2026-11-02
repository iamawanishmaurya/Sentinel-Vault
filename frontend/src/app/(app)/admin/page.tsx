"use client";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Glass, Mono, PageHeader, StatusBadge } from "@/components/bits";
import { Badge } from "@/components/ui/badge";
import { api, type User } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Row = User & { issuer: { name: string; address: string; authorized: boolean } | null };

export default function Admin() {
  const { user } = useAuth();
  const router = useRouter();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [names, setNames] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<number | null>(null);
  const load = useCallback(() => { api<Row[]>("/admin/users").then(setRows); }, []);
  useEffect(() => { if (user && user.role !== "admin") router.replace("/dashboard"); else load(); }, [user, router, load]);
  const act = async (id: number, fn: () => Promise<unknown>, ok: string) => {
    setBusy(id);
    try { await fn(); toast.success(ok); load(); } catch (e) { toast.error((e as Error).message); } finally { setBusy(null); }
  };
  return (
    <>
      <PageHeader title="Administration" subtitle="Approve issuers (creates an on-chain issuer identity) and manage accounts" />
      <Glass className="p-4">
        <Table>
          <TableHeader><TableRow><TableHead>User</TableHead><TableHead>Role</TableHead><TableHead>Status</TableHead><TableHead>Issuer wallet</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
          <TableBody>
            {rows?.map((u) => (
              <TableRow key={u.id}>
                <TableCell><div className="font-medium">{u.name}</div><div className="text-xs text-muted-foreground">{u.email}{u.organization && ` · ${u.organization}`}</div></TableCell>
                <TableCell><Badge variant="outline" className="capitalize border-cyan-400/30 text-cyan-300">{u.role}</Badge></TableCell>
                <TableCell><StatusBadge s={u.status === "active" ? "success" : u.status === "pending" ? "stored" : "failed"} /> <span className="text-xs text-muted-foreground capitalize">{u.status}</span></TableCell>
                <TableCell>{u.issuer ? <div><div className="text-xs">{u.issuer.name} · {u.issuer.authorized ? "authorised" : "removed"}</div><Mono value={u.issuer.address} /></div> : "—"}</TableCell>
                <TableCell className="text-right">
                  <div className="flex gap-2 justify-end items-center">
                    {busy === u.id && <Loader2 className="size-4 animate-spin" />}
                    {u.role === "issuer" && (!u.issuer || !u.issuer.authorized) && <>
                      <Input className="w-44 h-8" placeholder="Issuer name" value={names[u.id] ?? u.organization ?? ""} onChange={(e) => setNames({ ...names, [u.id]: e.target.value })} />
                      <Button size="sm" onClick={() => act(u.id, () => api(`/admin/users/${u.id}/approve-issuer`, { json: { issuer_name: names[u.id] ?? u.organization ?? u.name } }), "Issuer authorised on-chain")}>Approve</Button></>}
                    {u.issuer?.authorized && <Button size="sm" variant="destructive" onClick={() => act(u.id, () => api(`/admin/users/${u.id}/revoke-issuer`, { method: "POST" }), "Issuer removed on-chain")}>Remove issuer</Button>}
                    {u.role !== "admin" && u.status !== "pending" && <Button size="sm" variant="outline" onClick={() => act(u.id, () => api(`/admin/users/${u.id}/status`, { json: { status: u.status === "active" ? "disabled" : "active" } }), "Updated")}>{u.status === "active" ? "Disable" : "Enable"}</Button>}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Glass>
    </>
  );
}
