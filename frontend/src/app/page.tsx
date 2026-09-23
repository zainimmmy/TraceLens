"use client";

import { useCallback, useEffect, useState } from "react";
import DocumentView from "@/components/DocumentView";
import Dropzone from "@/components/Dropzone";
import ReportView from "@/components/ReportView";
import ServerStatus from "@/components/ServerStatus";
import { ACCEPT_ATTR, analyzeImage, analyzePdf, filesFromClipboard, isPdf, MAX_PDF_MB, MAX_UPLOAD_MB, validateFile } from "@/lib/api";
import type { AnalysisReport, PdfReport } from "@/lib/types";

const IMAGE_STEPS = ["Reading metadata and C2PA credentials", "Running the classifier and Grad-CAM", "Error Level Analysis and noise maps", "Writing the assessment"];
const PDF_STEPS = ["Opening the PDF", "Extracting the original embedded images", "Analysing each image", "Checking the document for later edits"];

const PASTE_NOTICE =
  "This image came from the clipboard. Copying an image usually strips its camera metadata and re-encodes it, which weakens the metadata and ELA checks. Upload the original file when you can.";

const MODULES = [
  { title: "AI classifier", body: "Fine-tuned EfficientNet estimates how likely the image is AI generated, with calibrated confidence." },
  { title: "Grad-CAM heatmap", body: "Shows which regions drove the classifier's decision, not just a bare score." },
  { title: "Classic forensics", body: "Error Level Analysis and noise residuals highlight pasted or edited regions." },
  { title: "Provenance", body: "Reads EXIF, XMP and C2PA credentials; flags stripped or inconsistent metadata." },
  { title: "Assessment", body: "Every signal is combined into a plain-English explanation and a PDF report." },
];

export default function Home() {
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [doc, setDoc] = useState<PdfReport | null>(null);
  const [openItem, setOpenItem] = useState<number | null>(null);
  const [busy, setBusy] = useState<"image" | "pdf" | null>(null);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [pasted, setPasted] = useState(false);

  const steps = busy === "pdf" ? PDF_STEPS : IMAGE_STEPS;

  useEffect(() => {
    if (!busy) return;
    const t = setInterval(() => setStep((s) => Math.min(s + 1, IMAGE_STEPS.length - 1)), busy === "pdf" ? 1800 : 900);
    return () => clearInterval(t);
  }, [busy]);

  useEffect(() => () => void (preview && URL.revokeObjectURL(preview)), [preview]);

  const reset = () => {
    setReport(null);
    setDoc(null);
    setOpenItem(null);
    setPreview(null);
    setPasted(false);
    setError(null);
  };

  const run = useCallback(async (files: File[], fromClipboard = false) => {
    const file = files[0];
    if (!file) return;
    const invalid = validateFile(file);
    if (invalid) {
      setError(invalid);
      return;
    }
    const pdf = isPdf(file);
    setError(null);
    setReport(null);
    setDoc(null);
    setOpenItem(null);
    setPasted(fromClipboard && !pdf);
    setPreview(pdf ? null : URL.createObjectURL(file));
    setStep(0);
    setBusy(pdf ? "pdf" : "image");
    try {
      if (pdf) setDoc(await analyzePdf(file));
      else setReport(await analyzeImage(file));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }, []);

  // Ctrl+V / Cmd+V anywhere on the page: on the start screen and on a report, to analyse the next image.
  useEffect(() => {
    if (busy) return;
    const onPaste = (e: ClipboardEvent) => {
      // Leave normal pasting into text fields alone. (The target can also be window or document.)
      if (e.target instanceof Element && e.target.closest("input, textarea, [contenteditable]")) return;
      const files = filesFromClipboard(e);
      if (files.length) {
        e.preventDefault();
        run(files, true);
      } else if (e.clipboardData?.getData("text")) {
        setError("The clipboard contains text, not an image. Copy an image (right-click → Copy image) or take a screenshot, then paste.");
      }
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [busy, run]);

  const next = (files: File[]) => run(files);
  const errorBanner = error && (
    <p role="alert" className="text-sm text-ai border-l-2 border-ai bg-ai-soft px-4 py-3" data-testid="error">
      {error}
    </p>
  );

  if (!busy && doc && openItem !== null && doc.items[openItem]?.report) {
    return (
      <div className="space-y-4">
        {errorBanner}
        <ReportView report={doc.items[openItem].report!} onNewFiles={next} onReset={reset} onBack={() => setOpenItem(null)} />
      </div>
    );
  }
  if (!busy && doc) {
    return (
      <div className="space-y-4">
        {errorBanner}
        <DocumentView doc={doc} onOpen={setOpenItem} onReset={reset} onNewFiles={next} />
      </div>
    );
  }
  if (!busy && report) {
    return (
      <div className="space-y-4">
        {errorBanner}
        <ReportView report={report} onNewFiles={next} onReset={reset} notice={pasted ? PASTE_NOTICE : null} />
      </div>
    );
  }

  return (
    <div className="space-y-12">
      <section className="max-w-3xl">
        <p className="label">
          <span className="label-num">■</span> Forensic image analysis · v1.0
        </p>
        <h1 className="font-display text-4xl sm:text-5xl font-semibold leading-[1.05] tracking-tight mt-4">
          Is this image real, AI generated, or edited<span className="text-accent">?</span>
        </h1>
        <p className="mt-5 text-muted text-lg leading-relaxed max-w-2xl">
          A trained classifier, classic image forensics and provenance metadata, combined into one explainable report. See exactly where and
          why, and defend the call.
        </p>
        <div className="mt-6">
          <ServerStatus />
        </div>
      </section>

      <section className="max-w-3xl space-y-3">
        {busy ? (
          <div className="panel p-6 flex flex-col sm:flex-row gap-6 items-center" data-testid="analyzing">
            <div className="relative w-40 h-40 overflow-hidden border border-border shrink-0 grid place-items-center bg-surface-2">
              {preview ? (
                // eslint-disable-next-line @next/next/no-img-element -- local object URL preview
                <img src={preview} alt="" className="w-full h-full object-cover opacity-80" />
              ) : (
                <span className="font-display text-2xl font-semibold text-accent tracking-widest">PDF</span>
              )}
              <div className="scanline absolute inset-x-0 top-0 h-1/4 bg-gradient-to-b from-transparent via-accent/35 to-transparent" />
            </div>
            <div className="font-mono text-[12px] space-y-2 w-full">
              <p className="label text-[10px] mb-3">
                <span className="label-num">■</span> Scan in progress
              </p>
              {steps.map((s, i) => (
                <p key={s} className={i <= step ? "text-text" : "text-faint"}>
                  <span className={i < step ? "text-real" : i === step ? "text-accent" : "text-faint"}>
                    [{i < step ? " OK " : i === step ? " .. " : "    "}]
                  </span>{" "}
                  {s}
                  {i === step && <span className="cursor-blink text-accent"> _</span>}
                </p>
              ))}
            </div>
          </div>
        ) : (
          <Dropzone
            onFiles={(files) => run(files)}
            accept={ACCEPT_ATTR}
            title="Drop an image or PDF here, click to choose, or paste"
            hint={`JPG · PNG · WEBP up to ${MAX_UPLOAD_MB} MB  //  PDF up to ${MAX_PDF_MB} MB  //  Ctrl+V to paste`}
          />
        )}
        {errorBanner}
        <p className="text-xs text-muted">
          Files are analysed in memory and discarded immediately. They are never stored, logged or sent to the summary model; only the numeric
          findings are.
        </p>
      </section>

      <section>
        <p className="label mb-4">
          <span className="label-num">■</span> Five analyses on every image
        </p>
        <div className="panel grid sm:grid-cols-2 lg:grid-cols-5 divide-y sm:divide-y-0 lg:divide-x divide-border">
          {MODULES.map((m, i) => (
            <div key={m.title} className="p-5">
              <p className="font-mono text-[11px] text-accent">F{i + 1}</p>
              <p className="font-display font-semibold text-[15px] tracking-wide uppercase mt-2">{m.title}</p>
              <p className="text-sm text-muted mt-2 leading-relaxed">{m.body}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
