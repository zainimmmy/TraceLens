import type { Metadata } from "next";
import type { ReactNode } from "react";
import { API_URL } from "@/lib/api";

export const metadata: Metadata = {
  title: "How it works · TraceLens",
  description: "How TraceLens combines a classifier, image forensics and provenance metadata into one explainable verdict.",
};

const SIGNALS = [
  {
    id: "F1",
    title: "AI image classifier",
    body: "An EfficientNet-B0 fine-tuned on real and AI-generated images from several generators, trained with JPEG and resize augmentation so it survives social media re-compression. Scores are temperature-calibrated so that 90% means roughly 90%. Wide images are scored with several crops and averaged.",
  },
  {
    id: "F2",
    title: "Grad-CAM heatmap",
    body: "Shows the regions that pushed the classifier towards “AI generated”. The heatmap is computed inside the exported ONNX graph, which lets the free CPU server produce it without PyTorch.",
  },
  {
    id: "F3",
    title: "Error Level Analysis and noise residuals",
    body: "ELA re-saves the image as a JPEG and measures how differently each block recompresses. The noise map strips image content with a median filter and compares local sensor noise. Both flag statistically unusual regions, not just bright pixels.",
  },
  {
    id: "F4",
    title: "Metadata and provenance",
    body: "Reads EXIF, XMP, PNG text chunks and C2PA content credentials. It looks for AI tool declarations (C2PA, IPTC digital source type, Stable Diffusion parameters), editing software, modify dates after capture, and stripped metadata.",
  },
  {
    id: "F5",
    title: "Plain-English assessment",
    body: "Gemini rewrites the structured findings into a short explanation. Only the numbers and findings are sent, never the image. If the free quota runs out, a template summary is used instead.",
  },
];

function Section({ num, title, children }: { num: string; title: string; children: ReactNode }) {
  return (
    <section className="border-t border-border pt-8">
      <p className="label">
        <span className="label-num">{num} {"//"}</span>
      </p>
      <h2 className="font-display text-2xl font-semibold tracking-wide mt-2">{title}</h2>
      <div className="mt-4 text-muted leading-relaxed space-y-3">{children}</div>
    </section>
  );
}

export default function About() {
  return (
    <article className="max-w-3xl space-y-10">
      <header>
        <p className="label">
          <span className="label-num">■</span> Methodology
        </p>
        <h1 className="font-display text-4xl sm:text-5xl font-semibold tracking-tight mt-4 leading-[1.05]">How TraceLens reaches a verdict</h1>
        <p className="mt-5 text-muted text-lg leading-relaxed">
          No single detector is reliable on its own, especially on image generators it has never seen. TraceLens runs five analyses in parallel and
          combines them with simple, readable rules, so every verdict can be explained.
        </p>
      </header>

      <Section num="00" title="In plain terms">
        <p>
          You give TraceLens an image. It asks five independent questions: does a trained AI model think it looks generated? Where in the picture
          did that model look? Do some areas compress or carry camera noise differently from the rest, as pasted or retouched areas do? What does the
          file&apos;s hidden metadata say about the camera, the software and any AI tool? Then it weighs the answers with fixed rules and writes a
          short explanation.
        </p>
      </Section>

      <div className="panel divide-y divide-border">
        {SIGNALS.map((s) => (
          <div key={s.id} className="p-5 grid sm:grid-cols-[4rem_1fr] gap-2">
            <p className="font-mono text-[12px] text-accent pt-1">{s.id}</p>
            <div>
              <h3 className="font-display font-semibold text-lg tracking-wide">{s.title}</h3>
              <p className="text-sm text-muted mt-1.5 leading-relaxed">{s.body}</p>
            </div>
          </div>
        ))}
      </div>

      <Section num="01" title="The decision rules">
        <ol className="space-y-2 list-decimal pl-5 marker:text-accent marker:font-mono">
          <li>If C2PA credentials, XMP metadata or an AI tool&apos;s own metadata declare the image AI generated, that wins.</li>
          <li>
            Otherwise the calibrated classifier decides AI vs real. Scores between <strong className="text-text">40% and 60%</strong> are reported
            as <em>inconclusive</em> rather than forced into a label.
          </li>
          <li>ELA, noise and metadata editing traces form a separate manipulation score. A high score gives an “edited or manipulated” verdict.</li>
          <li>Moderate manipulation evidence lowers the confidence of an “authentic” verdict and can make it inconclusive.</li>
        </ol>
      </Section>

      <Section num="02" title="PDFs and pasted images">
        <p>
          For a PDF, TraceLens pulls out the <strong className="text-text">original</strong> images embedded in it rather than taking a picture of
          the page, so each photo keeps its compression history and camera metadata. It also checks the PDF itself: how many times it was saved (later
          edits are appended as new revisions), whether it was modified after creation, and whether it was made with editing or AI software. PDFs with
          no photos are rendered page by page instead, which carries much less evidence.
        </p>
        <p>
          You can paste a copied image or screenshot with Ctrl+V. Copying usually strips camera metadata and re-encodes the image, so the report says
          so; upload the original file whenever you can.
        </p>
      </Section>

      <Section num="03" title="Limitations and ethics">
        <ul className="space-y-2 list-disc pl-5 marker:text-accent">
          <li>TraceLens gives probabilistic evidence, not proof. It should support human judgment, never replace it, especially when someone&apos;s reputation or money is at stake.</li>
          <li>Accuracy drops on generators the model has not seen. The published evaluation reports this honestly, alongside accuracy after JPEG compression and resizing.</li>
          <li>Social media strips metadata and re-compresses images, which weakens ELA and provenance signals. When possible, analyse the original file.</li>
          <li>Real photos can be flagged. That is why scores are calibrated, the inconclusive band exists, and every signal is shown.</li>
        </ul>
      </Section>

      <Section num="04" title="Privacy">
        <p>
          Uploads are processed in memory and discarded when the response is sent. Images are never written to disk, logged, or sent to the summary
          model. GPS coordinates in metadata are never shown; the report only says whether they exist. There are no accounts and no tracking.
        </p>
      </Section>

      <Section num="05" title="Use the API">
        <p>
          The same analysis is available as a JSON API. Interactive docs:{" "}
          <a className="text-accent hover:underline font-mono text-sm" href={`${API_URL}/docs`} target="_blank" rel="noreferrer">
            {API_URL}/docs
          </a>
        </p>
        <pre className="text-xs font-mono bg-bg border border-border border-l-2 border-l-accent p-4 overflow-x-auto text-text">
          {`curl -F "file=@photo.jpg" ${API_URL}/api/v1/analyze`}
        </pre>
      </Section>
    </article>
  );
}
