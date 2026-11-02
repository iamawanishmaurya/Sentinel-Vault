import Link from "next/link";
import { ArrowRight, Boxes, BrainCircuit, FileLock2, Fingerprint, Shield, ShieldCheck, Link2 } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";

const FEATURES = [
  { icon: FileLock2, title: "AES-256-GCM vault", text: "Every document is encrypted with its own random key before it touches storage. Keys are wrapped by a master key; ciphertext is authenticated." },
  { icon: Link2, title: "Ethereum-anchored integrity", text: "SHA-256 fingerprints are registered by authorised issuers in a Solidity smart contract — timestamped, attributable and revocable." },
  { icon: ShieldCheck, title: "Instant verification", text: "Upload any file. We hash it, query the chain and tell you: Verified, Modified, Unknown or Revoked — with the issuer and proof." },
  { icon: BrainCircuit, title: "Explainable fraud analytics", text: "Random Forest forensics (ELA, noise, OCR) and Isolation Forest behaviour analysis produce Low / Medium / High reports with reasons." },
  { icon: Boxes, title: "Blockchain explorer", text: "Inspect every transaction, block, issuer address and status straight from the node. Nothing is simulated." },
  { icon: Fingerprint, title: "Role-based access", text: "Admins, issuers, document owners and verifiers each see only what they should. Sharing is explicit and expiring." },
];

export default function Landing() {
  return (
    <div className="relative overflow-hidden">
      <div className="absolute inset-0 grid-bg pointer-events-none" />
      <header className="relative z-10 max-w-6xl mx-auto flex items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2 font-semibold">
          <div className="size-9 rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 grid place-items-center shadow-[0_0_24px_rgba(34,211,238,.45)]"><Shield className="size-5 text-white" /></div>
          Sentinel <span className="glow-text">Vault</span>
        </div>
        <div className="flex gap-2">
          <Link href="/login" className={buttonVariants({ variant: "ghost" })}>Sign in</Link>
          <Link href="/register" className={buttonVariants()}>Get started</Link>
        </div>
      </header>

      <section className="relative z-10 max-w-6xl mx-auto px-6 pt-16 pb-24 grid lg:grid-cols-2 gap-12 items-center">
        <div className="animate-in fade-in slide-in-from-left-6 duration-700">
          <div className="inline-flex items-center gap-2 text-xs rounded-full px-3 py-1 border border-cyan-400/30 bg-cyan-400/10 text-cyan-200 mb-6">
            <span className="size-1.5 rounded-full bg-cyan-300 animate-pulse" /> Blockchain-verified · ML-screened
          </div>
          <h1 className="text-5xl md:text-6xl font-semibold tracking-tight leading-[1.05]">
            Documents you can <span className="glow-text">prove</span>,<br />fraud you can <span className="glow-text">see</span>.
          </h1>
          <p className="mt-6 text-lg text-slate-300 max-w-xl">
            Sentinel Vault encrypts certificates and records, anchors their SHA-256 fingerprints on Ethereum, and uses machine learning to explain why a document or activity looks suspicious.
          </p>
          <div className="mt-8 flex gap-3">
            <Link href="/register" className={buttonVariants({ size: "lg" })}>Create account <ArrowRight className="size-4" /></Link>
            <Link href="/login" className={buttonVariants({ size: "lg", variant: "outline" })}>Verify a document</Link>
          </div>
        </div>

        <div className="relative animate-in fade-in zoom-in-95 duration-700 delay-150">
          <div className="glass rounded-2xl p-6 relative overflow-hidden">
            <div className="absolute inset-x-0 h-24 bg-gradient-to-b from-transparent via-cyan-400/15 to-transparent scanline" />
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm text-slate-300">certificate.pdf</span>
              <span className="text-xs px-2 py-1 rounded-md bg-emerald-500/15 text-emerald-300 border border-emerald-400/30">Verified</span>
            </div>
            {[["SHA-256", "8659b4…a7ebc8"], ["Issuer", "Northbridge University"], ["Block", "#4 · tx 0x1a32…3646"], ["Risk", "Low · RF 6% · IF 0%"]].map(([k, v]) => (
              <div key={k} className="flex justify-between py-2.5 border-b border-white/5 text-sm last:border-0"><span className="text-slate-400">{k}</span><span className="font-mono text-cyan-100/90">{v}</span></div>
            ))}
          </div>
        </div>
      </section>

      <section className="relative z-10 max-w-6xl mx-auto px-6 pb-24 grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {FEATURES.map(({ icon: Icon, title, text }) => (
          <div key={title} className="glass rounded-2xl p-6 transition-transform hover:-translate-y-1 hover:border-cyan-400/30">
            <div className="size-10 rounded-lg bg-cyan-400/10 grid place-items-center mb-4"><Icon className="size-5 text-cyan-300" /></div>
            <h3 className="font-medium mb-1.5">{title}</h3>
            <p className="text-sm text-slate-400 leading-relaxed">{text}</p>
          </div>
        ))}
      </section>
      <footer className="relative z-10 text-center text-xs text-slate-500 pb-8">Sentinel Vault · fraud models are trained on synthetic data for demonstration</footer>
    </div>
  );
}
