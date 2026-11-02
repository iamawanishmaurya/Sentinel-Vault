"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { Activity, Boxes, FileText, LayoutDashboard, LogOut, ScanSearch, Shield, ShieldCheck, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import type { Role } from "@/lib/api";

const NAV: { href: string; label: string; icon: React.ElementType; roles?: Role[] }[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/documents", label: "Documents", icon: FileText, roles: ["admin", "issuer", "owner"] },
  { href: "/verify", label: "Verify", icon: ShieldCheck },
  { href: "/analytics", label: "Fraud Analytics", icon: ScanSearch },
  { href: "/explorer", label: "Blockchain Explorer", icon: Boxes },
  { href: "/admin", label: "Administration", icon: Users, roles: ["admin"] },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const path = usePathname();
  const router = useRouter();
  useEffect(() => { if (!loading && !user) router.replace("/login"); }, [loading, user, router]);
  if (loading || !user) return <div className="min-h-screen grid place-items-center"><Shield className="size-10 text-cyan-300 animate-pulse" /></div>;
  const items = NAV.filter((n) => !n.roles || n.roles.includes(user.role));
  return (
    <div className="min-h-screen flex">
      <aside className="hidden md:flex w-64 shrink-0 flex-col border-r border-white/10 bg-[#08122a]/80 backdrop-blur-xl p-4 sticky top-0 h-screen">
        <Link href="/" className="flex items-center gap-2 px-2 py-3 mb-4">
          <div className="size-9 rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 grid place-items-center shadow-[0_0_24px_rgba(34,211,238,.45)]"><Shield className="size-5 text-white" /></div>
          <div className="font-semibold tracking-tight">Sentinel <span className="glow-text">Vault</span></div>
        </Link>
        <nav className="space-y-1 flex-1">
          {items.map(({ href, label, icon: Icon }) => {
            const active = path === href || path.startsWith(href + "/");
            return (
              <Link key={href} href={href} className={cn("flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                active ? "bg-cyan-400/10 text-cyan-200 ring-1 ring-cyan-400/25" : "text-slate-400 hover:text-slate-100 hover:bg-white/5")}>
                <Icon className="size-4" />{label}
              </Link>
            );
          })}
        </nav>
        <div className="glass rounded-xl p-3 text-sm">
          <div className="font-medium truncate">{user.name}</div>
          <div className="text-xs text-muted-foreground truncate mb-2">{user.email}</div>
          <div className="flex items-center justify-between">
            <Badge variant="outline" className="capitalize border-cyan-400/30 text-cyan-300">{user.role}</Badge>
            <Button size="icon-sm" variant="ghost" onClick={logout} title="Sign out"><LogOut className="size-4" /></Button>
          </div>
        </div>
      </aside>
      <div className="flex-1 min-w-0">
        <header className="md:hidden flex items-center justify-between px-4 py-3 border-b border-white/10 bg-[#08122a]/80 backdrop-blur-xl sticky top-0 z-20">
          <div className="flex items-center gap-2 font-semibold"><Activity className="size-5 text-cyan-300" />Sentinel Vault</div>
          <Button size="sm" variant="ghost" onClick={logout}><LogOut className="size-4" /></Button>
        </header>
        <nav className="md:hidden flex gap-1 overflow-x-auto px-3 py-2 border-b border-white/10">
          {items.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} className={cn("flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-xs", path.startsWith(href) ? "bg-cyan-400/15 text-cyan-200" : "text-slate-400")}><Icon className="size-3.5" />{label}</Link>
          ))}
        </nav>
        <main className="p-4 md:p-8 max-w-[1400px] mx-auto animate-in fade-in slide-in-from-bottom-2 duration-500">{children}</main>
      </div>
    </div>
  );
}
