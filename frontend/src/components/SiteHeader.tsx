"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { API_URL } from "@/lib/api";

const NAV: { href: string; label: string; short?: string }[] = [
  { href: "/", label: "Analyze" },
  { href: "/batch", label: "Batch" },
  { href: "/about", label: "How it works", short: "About" },
];

/** Targeting reticle mark. */
export function Logo({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className="text-accent">
      <path d="M2 8V2h6M16 2h6v6M22 16v6h-6M8 22H2v-6" fill="none" stroke="currentColor" strokeWidth="2" />
      <rect x="9" y="9" width="6" height="6" fill="currentColor" />
    </svg>
  );
}

export default function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-20 bg-bg/95 border-b border-border">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2 sm:gap-3 shrink-0">
          <Logo />
          <span className="font-display font-semibold text-[15px] tracking-[0.14em] sm:tracking-[0.22em]">TRACELENS</span>
          <span className="hidden md:inline label text-[10px] text-faint">{"// Image forensics"}</span>
        </Link>
        <nav className="flex items-center">
          {NAV.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`px-2 sm:px-3.5 h-14 inline-flex items-center font-mono text-[11px] tracking-[0.08em] sm:tracking-[0.14em] uppercase whitespace-nowrap border-b-2 transition-colors ${
                  active ? "border-accent text-text" : "border-transparent text-muted hover:text-text"
                }`}
              >
                {item.short ? (
                  <>
                    <span className="sm:hidden">{item.short}</span>
                    <span className="hidden sm:inline">{item.label}</span>
                  </>
                ) : (
                  item.label
                )}
              </Link>
            );
          })}
          <a
            href={`${API_URL}/docs`}
            target="_blank"
            rel="noreferrer"
            className="hidden sm:inline-flex px-3.5 h-14 items-center font-mono text-[11px] tracking-[0.14em] uppercase text-muted hover:text-text border-b-2 border-transparent"
          >
            API ↗
          </a>
        </nav>
      </div>
    </header>
  );
}
