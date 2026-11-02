"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Loader2, Shield } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";

export default function Login() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true);
    try { await login(email, pw); router.replace("/dashboard"); } catch (err) { toast.error((err as Error).message); } finally { setBusy(false); }
  }
  return (
    <div className="min-h-screen grid place-items-center p-4 relative">
      <div className="absolute inset-0 grid-bg pointer-events-none" />
      <form onSubmit={submit} className="glass rounded-2xl p-8 w-full max-w-md relative animate-in fade-in zoom-in-95 duration-500 space-y-5">
        <div className="text-center">
          <div className="size-12 mx-auto rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 grid place-items-center shadow-[0_0_30px_rgba(34,211,238,.45)] mb-4"><Shield className="size-6 text-white" /></div>
          <h1 className="text-2xl font-semibold">Welcome back</h1>
          <p className="text-sm text-muted-foreground">Sign in to Sentinel Vault</p>
        </div>
        <div className="space-y-2"><Label htmlFor="email">Email</Label><Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" /></div>
        <div className="space-y-2"><Label htmlFor="pw">Password</Label><Input id="pw" type="password" required value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="current-password" /></div>
        <Button type="submit" className="w-full" disabled={busy}>{busy && <Loader2 className="size-4 animate-spin" />}Sign in</Button>
        <p className="text-center text-sm text-muted-foreground">No account? <Link href="/register" className="text-cyan-300 hover:underline">Register</Link></p>
      </form>
    </div>
  );
}
