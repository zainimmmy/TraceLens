import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import { mockApi, pdfReport, sampleImage, samplePdf } from "./mock-api";

/** Fire a real paste event carrying a file, like Ctrl+V after "Copy image" or a screenshot. */
async function pasteFile(page: Page, filePath: string, name: string, type: string) {
  const b64 = fs.readFileSync(filePath).toString("base64");
  await page.evaluate(
    ({ b64, name, type }) => {
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      const dt = new DataTransfer();
      dt.items.add(new File([bytes], name, { type }));
      window.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true }));
    },
    { b64, name, type },
  );
}

test("a PDF shows the document report and each embedded image", async ({ page }) => {
  const calls = await mockApi(page);
  await page.goto("/");
  await page.getByTestId("file-input").setInputFiles(samplePdf);

  await expect(page.getByTestId("document-report")).toBeVisible();
  expect(calls).toContain("POST /api/v1/analyze/pdf");
  await expect(page.getByTestId("document-verdict")).toHaveText("The PDF shows signs of editing");
  await expect(page.getByTestId("document-integrity")).toContainText("saved revisions");
  const items = page.getByTestId("document-items").getByRole("button");
  await expect(items).toHaveCount(pdfReport.items.length);
  await expect(items.first()).toContainText("Original JPEG from the PDF");

  await items.first().click();
  await expect(page.getByTestId("verdict-label")).toBeVisible();
  await expect(page.getByTestId("metadata-panel")).toContainText("Adobe Photoshop");
  await page.getByTestId("back-to-document").click();
  await expect(page.getByTestId("document-report")).toBeVisible();
});

test("pasting a copied image analyses it and explains the clipboard caveat", async ({ page }) => {
  const calls = await mockApi(page);
  await page.goto("/");
  await expect(page.getByTestId("dropzone")).toBeVisible();
  await pasteFile(page, sampleImage, "image.png", "image/png");

  await expect(page.getByTestId("verdict-label")).toBeVisible();
  await expect(page.getByTestId("notice")).toContainText("clipboard");
  expect(calls).toContain("POST /api/v1/analyze");
});

test("pasting text explains how to paste an image", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByTestId("dropzone")).toBeVisible();
  await page.evaluate(() => {
    const dt = new DataTransfer();
    dt.setData("text/plain", "https://example.com/photo.jpg");
    window.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt }));
  });
  await expect(page.getByTestId("error")).toContainText("not an image");
});

test("batch page accepts pasted images and PDFs", async ({ page }) => {
  await mockApi(page);
  await page.goto("/batch");
  await expect(page.getByTestId("dropzone")).toBeVisible();
  await pasteFile(page, sampleImage, "image.png", "image/png");
  await page.getByTestId("file-input").setInputFiles(samplePdf);
  await expect(page.getByText(/^pasted-image-\d{6}\.png$/)).toBeVisible();
  await expect(page.getByText("sample.pdf")).toBeVisible();
  await expect(page.getByRole("button", { name: /Analyze 2 file/ })).toBeVisible();
});
