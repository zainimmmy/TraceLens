"use client";

import { useCallback, useEffect, useState } from "react";
import DocumentView from "@/components/DocumentView";
import Dropzone from "@/components/Dropzone";
import ReportView from "@/components/ReportView";
import ServerStatus from "@/components/ServerStatus";
import { ACCEPT_ATTR, analyzeImage, analyzePdf, filesFromClipboard, isPdf, MAX_PDF_MB, MAX_UPLOAD_MB, validateFile } from "@/lib/api";
import type { AnalysisReport, PdfReport } from "@/lib/types";

const IMAGE_STEPS = ["Reading metadata and C2PA credentials", "Running the classifier and Grad-CAM", "Error Level Analysis and noise maps", "Writing the summary"];
const PDF_STEPS = ["Opening the PDF", "Extracting the original embedded images", "Analysing each image", "Checking the document for later edits"];

const PASTE_NOTICE =
  "This image came from the clipboard. Copying an image usually strips its camera metadata and re-encodes it, which weakens the metadata and ELA checks. Upload the original file when you can.";

const MODULES = [
  { title: "AI classifier", body: "A fine-tuned EfficientNet estimates how likely the image is AI generated, with calibrated confidence." },
  { title: "Grad-CAM heatmap", body: "Shows which regions drove the classifier's decision, not just a bare score." },
  { title: "Classic forensics", body: "Error Level Analysis and noise residuals highlight pasted or edited regions." },
  { title: "Provenance", body: "Reads EXIF, XMP and C2PA content credentials, and flags stripped or inconsistent metadata." },
  { title: "Plain-English report", body: "Every signal is combined into a short explanation and a downloadable PDF." },
];

function PdfIcon() {
  return (
    <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
      <text x="12" y="17" fontSize="5" textAnchor="middle" fill="currentColor" stroke="none" fontWeight="700">
        PDF
      </text>
    </svg>
  );
}

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

  // Ctrl+V / Cmd+V anywhere on the page, while the upload area is showing.
  const idle = !busy && !report && !doc;
  useEffect(() => {
    if (!idle) return;
    const onPaste = (e: ClipboardEvent) => {
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
  }, [idle, run]);

  if (doc && openItem !== null && doc.items[openItem]?.report) {
    return <ReportView report={doc.items[openItem].report!} onReset={reset} onBack={() => setOpenItem(null)} />;
  }
  if (doc) return <DocumentView doc={doc} onOpen={setOpenItem} onReset={reset} />;
  if (report) return <ReportView report={report} onReset={reset} notice={pasted ? PASTE_NOTICE : null} />;

  return (
    <div className="space-y-10">
      <section className="max-w-3xl">
        <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">Is this image real, AI generated, or edited?</h1>
        <p className="mt-3 text-muted text-lg leading-relaxed">
          TraceLens combines a trained classifier, classic image forensics and provenance metadata into one explainable report, so you can see exactly
          where and why, and defend the call.
        </p>
        <div className="mt-3">
          <ServerStatus />
        </div>
      </section>

      <section className="max-w-3xl">
        {busy ? (
          <div className="card p-6 flex flex-col sm:flex-row gap-6 items-center" data-testid="analyzing">
            <div className="relative w-40 h-40 rounded-lg overflow-hidden border border-border shrink-0 grid place-items-center text-accent bg-surface-2">
              {preview ? (
                // eslint-disable-next-line @next/next/no-img-element -- local object URL preview
                <img src={preview} alt="" className="w-full h-full object-cover" />
              ) : (
                <PdfIcon />
              )}
              <div className="scanline absolute inset-x-0 top-0 h-1/4 bg-gradient-to-b from-transparent via-accent/40 to-transparent" />
            </div>
            <ol className="space-y-2 text-sm">
              {steps.map((s, i) => (
                <li key={s} className={`flex items-center gap-2 ${i <= step ? "text-text" : "text-muted/60"}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${i < step ? "bg-real" : i === step ? "bg-accent animate-pulse" : "bg-border"}`} />
                  {s}
                </li>
              ))}
            </ol>
          </div>
        ) : (
          <Dropzone
            onFiles={(files) => run(files)}
            accept={ACCEPT_ATTR}
            title="Drop an image or PDF here, click to choose, or paste"
            hint={`JPG, PNG or WEBP up to ${MAX_UPLOAD_MB} MB · PDF up to ${MAX_PDF_MB} MB · paste a copied image or screenshot with Ctrl+V`}
          />
        )}
        {error && (
          <p role="alert" className="mt-3 text-sm text-ai" data-testid="error">
            {error}
          </p>
        )}
        <p className="mt-3 text-xs text-muted">
          Your file is analysed in memory and discarded immediately. It is never stored, logged or sent to the summary model; only the numeric
          findings are.
        </p>
      </section>

      <section>
        <h2 className="text-sm font-medium text-muted mb-3">Five analyses run on every image</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {MODULES.map((m, i) => (
            <div key={m.title} className="card p-4">
              <p className="text-xs font-mono text-accent">F{i + 1}</p>
              <p className="font-medium mt-1">{m.title}</p>
              <p className="text-sm text-muted mt-1 leading-relaxed">{m.body}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
