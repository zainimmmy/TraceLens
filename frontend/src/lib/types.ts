export type Verdict = "ai_generated" | "manipulated" | "real" | "inconclusive";

export interface Region {
  x: number;
  y: number;
  width: number;
  height: number;
  share: number;
}

export interface Finding {
  signal: string;
  points_to: string;
  strength: "high" | "medium" | "low" | "info";
  text: string;
}

export interface MetadataFlag {
  code: string;
  severity: string;
  points_to: string;
  message: string;
}

export interface C2paInfo {
  present: boolean;
  validated: boolean;
  claim_generator?: string | null;
  signed_by?: string | null;
  signed_at?: string | null;
  actions?: string[];
  digital_source_types?: string[];
  declares_ai?: boolean;
  validation_errors?: string[];
  error?: string;
}

export interface MetadataSignal {
  exif_present: boolean;
  camera: { make?: string; model?: string } | null;
  software_tag: string | null;
  dates: { original?: string | null; digitized?: string | null; modified?: string | null };
  gps_present: boolean;
  xmp: Record<string, string> | null;
  png_text_keys: string[] | null;
  c2pa_manifest: C2paInfo | null;
  ai_generator_hint: { source: string; match: string } | null;
  flags: MetadataFlag[];
  exif: Record<string, string | number>;
}

export interface AnalysisReport {
  id: string;
  filename: string | null;
  analyzed_at: string;
  verdict: Verdict;
  verdict_label: string;
  confidence: number;
  ai_probability: number | null;
  ai_probability_source: string | null;
  manipulation_score: number;
  manipulation_breakdown: Record<string, number>;
  verdict_basis: string;
  signals: {
    classifier: { available: boolean; ai_probability: number | null; model: string | null; crop_probabilities?: number[] };
    frequency: { high_to_mid_ratio: number; baseline_ai_probability: number | null };
    ela: { reliability: string; max_error_level: number; mean_error_level: number; suspicious_regions: number; regions: Region[] };
    noise: { median_noise_level?: number; inconsistent_blocks_share: number; suspicious_regions: number; regions: Region[] };
    metadata: MetadataSignal;
    heatmap_url: string | null;
  };
  findings: Finding[];
  summary: string;
  summary_source: "gemini" | "template";
  images: { original?: string; gradcam?: string | null; ela?: string; noise?: string };
  image_info: { format: string; width: number; height: number; bytes: number };
  timings_ms: Record<string, number>;
  version: string;
  disclaimer: string;
}

export interface BatchItem {
  filename: string;
  verdict: Verdict | null;
  verdict_label: string | null;
  confidence: number | null;
  ai_probability: number | null;
  manipulation_score: number | null;
  summary: string | null;
  error: string | null;
}

export interface BatchReport {
  count: number;
  counts_by_verdict: Record<string, number>;
  items: BatchItem[];
  disclaimer: string;
}

export interface Health {
  status: "ok";
  version: string;
  classifier: { loaded: boolean; model?: string; reason?: string; metrics?: Record<string, unknown> };
  llm_summaries: boolean;
}

export interface DocumentFlag {
  code: string;
  severity: "high" | "medium" | "low" | "info";
  points_to: string;
  message: string;
}

export interface PdfItem {
  name: string;
  page: number;
  source: "embedded" | "rendered_page";
  embedded_format: string;
  report: AnalysisReport | null;
  error: string | null;
}

export interface PdfReport {
  filename: string | null;
  kind: "pdf";
  overall_verdict: Verdict;
  overall_basis: "images" | "document";
  counts_by_verdict: Record<string, number>;
  summary: string;
  document: {
    pages: number;
    title?: string | null;
    author?: string | null;
    creator?: string | null;
    producer?: string | null;
    created?: string | null;
    modified?: string | null;
    revisions: number;
  };
  document_flags: DocumentFlag[];
  extraction: {
    mode: "embedded_images" | "rendered_pages";
    images_found: number;
    images_analyzed: number;
    skipped_small: number;
    skipped_duplicate: number;
    truncated: boolean;
  };
  items: PdfItem[];
  disclaimer: string;
}
