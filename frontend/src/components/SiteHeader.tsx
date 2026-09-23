"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { API_URL } from "@/lib/api";

const NAV = [
  { href: "/", label: "Analyze" },
  { href: "/batch", label: "Batch" },
  { href: "/about", label: "How it works" },
];

export function Logo() {
  return (
    <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="14" cy="14" r="9" fill="none" stroke="currentColor" strokeWidth="2.5" />
      <path d="M20.5 20.5 L28 28" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      <path d="M9 15 l3 -4 l3 5 l2 -3" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

export default function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="border-b border-border bg-surface/80 backdrop-blur sticky top-0 z-20">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight text-text">
          <span className="text-accent">
            <Logo />
          </span>
          TraceLens
        </Link>
        <nav className="flex items-center gap-0.5 sm:gap-1 text-sm">
          {NAV.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`px-2 sm:px-3 py-1.5 rounded-lg whitespace-nowrap transition-colors ${
                  active ? "bg-accent-soft text-accent font-medium" : "text-muted hover:text-text"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
          <a
            href={`${API_URL}/docs`}
            target="_blank"
            rel="noreferrer"
            className="hidden sm:inline px-3 py-1.5 rounded-lg text-muted hover:text-text"
          >
            API
          </a>
        </nav>
      </div>
    </header>
  );
}
