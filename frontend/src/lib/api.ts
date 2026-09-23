import type { AnalysisReport, BatchReport, Health, PdfReport } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export const MAX_UPLOAD_MB = 10;
export const MAX_PDF_MB = 20;
export const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const ACCEPT_ATTR = "image/jpeg,image/png,image/webp,application/pdf,.pdf";

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
  }
}

async function request(path: string, init?: RequestInit, timeoutMs = 90_000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, signal: controller.signal });
  } catch (err) {
    if ((err as Error).name === "AbortError") {
      throw new ApiError("The server took too long to respond. It may be waking up; please try again.");
    }
    throw new ApiError("Could not reach the TraceLens server. Check your connection and try again.");
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    let detail = `Request failed (HTTP ${res.status}).`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, res.status);
  }
  return res;
}

export async function getHealth(): Promise<Health> {
  return (await request("/api/v1/health", undefined, 60_000)).json();
}

export async function analyzeImage(file: File): Promise<AnalysisReport> {
  const form = new FormData();
  form.append("file", file);
  return (await request("/api/v1/analyze", { method: "POST", body: form })).json();
}

export async function analyzePdf(file: File): Promise<PdfReport> {
  const form = new FormData();
  form.append("file", file);
  return (await request("/api/v1/analyze/pdf", { method: "POST", body: form }, 180_000)).json();
}

export async function analyzeBatch(files: File[]): Promise<BatchReport> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  return (await request("/api/v1/analyze/batch", { method: "POST", body: form }, 300_000)).json();
}

export async function downloadPdf(report: AnalysisReport): Promise<void> {
  const res = await request("/api/v1/report/pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(report),
  });
  saveBlob(await res.blob(), `tracelens-report-${safeName(report.filename)}.pdf`);
}

export function downloadJson(report: AnalysisReport): void {
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
  saveBlob(blob, `tracelens-report-${safeName(report.filename)}.json`);
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function safeName(name: string | null): string {
  return (name || "image").replace(/\.[^.]+$/, "").replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 60) || "image";
}

export function isPdf(file: File): boolean {
  return file.type === "application/pdf" || /\.pdf$/i.test(file.name);
}

export function validateFile(file: File): string | null {
  if (isPdf(file)) {
    return file.size > MAX_PDF_MB * 1024 * 1024 ? `"${file.name}" is larger than ${MAX_PDF_MB} MB.` : null;
  }
  if (!IMAGE_TYPES.includes(file.type)) return `"${file.name}" is not a JPG, PNG, WEBP image or a PDF.`;
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `"${file.name}" is larger than ${MAX_UPLOAD_MB} MB.`;
  return null;
}

/** Files from a paste event: screenshots, "Copy image" from a browser, or files copied in Explorer/Finder. */
export function filesFromClipboard(e: ClipboardEvent): File[] {
  const files: File[] = [];
  for (const item of Array.from(e.clipboardData?.items ?? [])) {
    if (item.kind !== "file") continue;
    const f = item.getAsFile();
    if (!f) continue;
    // Clipboard images are usually called "image.png"; give them a recognisable name.
    const generic = !f.name || /^image\.(png|jpe?g|webp)$/i.test(f.name);
    const ext = (f.type.split("/")[1] || "png").replace("jpeg", "jpg");
    const stamp = new Date().toTimeString().slice(0, 8).replace(/:/g, "");
    files.push(generic ? new File([f], `pasted-image-${stamp}.${ext}`, { type: f.type }) : f);
  }
  return files;
}
