import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Chakra_Petch, Geist, Geist_Mono } from "next/font/google";
import SiteHeader from "@/components/SiteHeader";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
const display = Chakra_Petch({ variable: "--font-display-face", subsets: ["latin"], weight: ["500", "600", "700"] });

export const metadata: Metadata = {
  title: "TraceLens: AI image and deepfake detection",
  description:
    "Free, open source image forensics. Find out whether an image is real, AI generated or edited, and see exactly where and why.",
};

// Explicit prop type rather than Next's generated LayoutProps helper: those types only exist
// after `next dev`/`next build`, and CI type-checks before building.
export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} ${display.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <SiteHeader />
        <main className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-6 py-10">{children}</main>
        <footer className="border-t border-border">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-5 flex flex-wrap gap-x-8 gap-y-2 justify-between label text-[10px]">
            <span>
              <span className="label-num">■</span> Probabilistic evidence, not proof. Supports human judgment, never replaces it.
            </span>
            <span>No images stored · processed in memory</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
