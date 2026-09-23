import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import SiteHeader from "@/components/SiteHeader";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "TraceLens: AI image and deepfake detection",
  description:
    "Free, open source image forensics. Find out whether an image is real, AI generated or edited, and see exactly where and why.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <SiteHeader />
        <main className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-6 py-8">{children}</main>
        <footer className="border-t border-border text-muted text-xs">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-5 flex flex-wrap gap-x-6 gap-y-2 justify-between">
            <span>TraceLens gives probabilistic evidence, not proof. It supports human judgment and never replaces it.</span>
            <span>Images are analysed in memory and never stored.</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
