import { expect, test } from "@playwright/test";
import { mockApi, report, sampleImage } from "./mock-api";

test("home page shows the upload area and server status", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /real, AI generated, or edited/i })).toBeVisible();
  await expect(page.getByTestId("dropzone")).toBeVisible();
  await expect(page.getByTestId("server-status")).toContainText("efficientnet_b0_v1");
});

test("analyzing an image shows the full report", async ({ page }) => {
  const calls = await mockApi(page);
  await page.goto("/");
  await page.getByTestId("file-input").setInputFiles(sampleImage);

  await expect(page.getByTestId("verdict-label")).toHaveText(report.verdict_label);
  await expect(page.getByTestId("summary")).toContainText(report.summary.slice(0, 40));
  await expect(page.getByTestId("findings")).toContainText("Error Level Analysis");
  await expect(page.getByTestId("metadata-panel")).toContainText("Adobe Photoshop");
  await expect(page.getByTestId("disclaimer")).toContainText("probabilistic");
  expect(calls).toContain("POST /api/v1/analyze");

  // switch evidence layers
  const viewer = page.getByTestId("evidence-viewer");
  await viewer.getByRole("tab", { name: "Noise consistency" }).click();
  await expect(viewer.getByRole("tab", { name: "Noise consistency" })).toHaveAttribute("aria-selected", "true");
  await expect(viewer.getByAltText("Noise consistency overlay")).toBeVisible();

  // PDF download
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download PDF report" }).click();
  expect((await download).suggestedFilename()).toBe("tracelens-report-sample.pdf");
  expect(calls).toContain("POST /api/v1/report/pdf");

  await page.getByRole("button", { name: "New scan" }).click();
  await expect(page.getByTestId("dropzone")).toBeVisible();
});

test("the next image can be analysed straight from a report", async ({ page }) => {
  const calls = await mockApi(page);
  const analyses = () => calls.filter((c) => c === "POST /api/v1/analyze").length;
  await page.goto("/");
  await page.getByTestId("file-input").setInputFiles(sampleImage);
  await expect(page.getByTestId("verdict-label")).toBeVisible();

  // the "analyze another" bar sits above the report
  await expect(page.getByTestId("quick-upload")).toBeVisible();
  await page.getByTestId("quick-upload").locator("input[type=file]").setInputFiles(sampleImage);
  await expect.poll(analyses).toBe(2);
  await expect(page.getByTestId("verdict-label")).toBeVisible();

  // Ctrl+V on a report analyses the pasted image too
  await page.evaluate(() => {
    const dt = new DataTransfer();
    dt.items.add(new File([new Uint8Array([0xff, 0xd8, 0xff])], "image.png", { type: "image/png" }));
    window.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt }));
  });
  await expect.poll(analyses).toBe(3);
  await expect(page.getByTestId("notice")).toContainText("clipboard");
});

test("unsupported files are rejected before upload", async ({ page }) => {
  const calls = await mockApi(page);
  await page.goto("/");
  await page.getByTestId("file-input").setInputFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("hi") });
  await expect(page.getByTestId("error")).toContainText("not a JPG, PNG, WEBP image or a PDF");
  expect(calls).not.toContain("POST /api/v1/analyze");
});

test("API errors are shown to the user", async ({ page }) => {
  await mockApi(page, { analyzeStatus: 429, analyzeDetail: "Too many requests. Please wait a minute and try again." });
  await page.goto("/");
  await page.getByTestId("file-input").setInputFiles(sampleImage);
  await expect(page.getByTestId("error")).toContainText("Too many requests");
});

test("batch mode shows a summary table", async ({ page }) => {
  await mockApi(page);
  await page.goto("/batch");
  await page.getByTestId("file-input").setInputFiles([sampleImage, sampleImage]);
  await page.getByRole("button", { name: /Analyze 2 file/ }).click();
  const table = page.getByTestId("batch-report");
  await expect(table).toContainText("a.jpg");
  await expect(table).toContainText("Likely an authentic photo");
});

test("about page explains the method and ethics", async ({ page }) => {
  await page.goto("/about");
  await expect(page.getByRole("heading", { name: "Limitations and ethics" })).toBeVisible();
  await expect(page.getByText("40% and 60%")).toBeVisible();
});
