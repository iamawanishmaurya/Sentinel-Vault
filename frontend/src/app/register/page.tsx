"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Loader2, Shield } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const ROLES = [
  { v: "owner", t: "Document Owner", d: "Store & share encrypted documents" },
  { v: "verifier", t: "Verifier", d: "Verify documents (employers, agencies)" },
  { v: "issuer", t: "Issuer", d: "Universities & authorities · needs admin approval" },
];

export default function Register() {
  const router = useRouter();
  const [f, setF] = useState({ name: "", email: "", password: "", organization: "", role: "owner" });
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true);
    try {
      const r = await api<{ message: string }>("/auth/register", { json: { ...f, organization: f.organization || null } });
      toast.success(r.message); router.push("/login");
    } catch (err) { toast.error((err as Error).message); } finally { setBusy(false); }
  }
  return (
    <div className="min-h-screen grid place-items-center p-4 relative">
      <div className="absolute inset-0 grid-bg pointer-events-none" />
      <form onSubmit={submit} className="glass rounded-2xl p-8 w-full max-w-lg relative animate-in fade-in zoom-in-95 duration-500 space-y-4">
        <div className="text-center">
          <div className="size-12 mx-auto rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 grid place-items-center mb-3"><Shield className="size-6 text-white" /></div>
          <h1 className="text-2xl font-semibold">Create your account</h1>
        </div>
        <div className="grid sm:grid-cols-3 gap-2">
          {ROLES.map((r) => (
            <button type="button" key={r.v} onClick={() => setF({ ...f, role: r.v })}
              className={cn("rounded-xl border p-3 text-left transition-colors", f.role === r.v ? "border-cyan-400/60 bg-cyan-400/10" : "border-white/10 hover:border-white/25")}>
              <div className="text-sm font-medium">{r.t}</div><div className="text-[11px] text-muted-foreground mt-1">{r.d}</div>
            </button>
          ))}
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="space-y-2"><Label>Full name</Label><Input required minLength={2} value={f.name} onChange={set("name")} /></div>
          <div className="space-y-2"><Label>Organization</Label><Input value={f.organization} onChange={set("organization")} /></div>
        </div>
        <div className="space-y-2"><Label>Email</Label><Input type="email" required value={f.email} onChange={set("email")} /></div>
        <div className="space-y-2"><Label>Password <span className="text-muted-foreground">(min 10 characters)</span></Label><Input type="password" required minLength={10} value={f.password} onChange={set("password")} autoComplete="new-password" /></div>
        <Button type="submit" className="w-full" disabled={busy}>{busy && <Loader2 className="size-4 animate-spin" />}Create account</Button>
        <p className="text-center text-sm text-muted-foreground">Already registered? <Link href="/login" className="text-cyan-300 hover:underline">Sign in</Link></p>
      </form>
    </div>
  );
}
