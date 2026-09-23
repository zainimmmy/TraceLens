import type { Page, Route } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const report = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "report.json"), "utf8"));
export const sampleImage = path.join(__dirname, "fixtures", "sample.jpg");
export const samplePdf = path.join(__dirname, "fixtures", "sample.pdf");
export const pdfReport = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "pdf_report.json"), "utf8"));

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

export async function mockApi(page: Page, overrides: { analyzeStatus?: number; analyzeDetail?: string } = {}) {
  const calls: string[] = [];
  await page.route(`${API}/api/v1/**`, async (route) => {
    const url = new URL(route.request().url());
    calls.push(`${route.request().method()} ${url.pathname}`);
    switch (url.pathname) {
      case "/api/v1/health":
        return json(route, { status: "ok", version: "1.0.0", classifier: { loaded: true, model: "efficientnet_b0_v1" }, llm_summaries: false });
      case "/api/v1/analyze":
        if (overrides.analyzeStatus) return json(route, { detail: overrides.analyzeDetail ?? "error" }, overrides.analyzeStatus);
        return json(route, report);
      case "/api/v1/analyze/pdf":
        return json(route, pdfReport);
      case "/api/v1/analyze/batch":
        return json(route, {
          count: 2,
          counts_by_verdict: { manipulated: 1, real: 1 },
          disclaimer: report.disclaimer,
          items: [
            { filename: "a.jpg", verdict: "manipulated", verdict_label: "Likely edited or manipulated", confidence: 0.84, ai_probability: 0.2, manipulation_score: 0.84, summary: "Edited.", error: null },
            { filename: "b.jpg", verdict: "real", verdict_label: "Likely an authentic photo", confidence: 0.91, ai_probability: 0.09, manipulation_score: 0, summary: "Looks real.", error: null },
          ],
        });
      case "/api/v1/report/pdf":
        return route.fulfill({ status: 200, contentType: "application/pdf", body: Buffer.from("%PDF-1.4 mock") });
      default:
        return route.fulfill({ status: 404 });
    }
  });
  return calls;
}
