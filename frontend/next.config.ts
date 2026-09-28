import type { NextConfig } from "next";

// GitHub Pages serves plain files, so its build (STATIC_EXPORT=1, see
// .github/workflows/pages.yml) exports the site as static HTML into `out/`. A project site
// lives under /<repo-name>/, which PAGES_BASE_PATH supplies. Local dev is unaffected.
const staticExport = process.env.STATIC_EXPORT === "1";

const nextConfig: NextConfig = staticExport
  ? {
      output: "export",
      basePath: process.env.PAGES_BASE_PATH || "",
      trailingSlash: true, // /batch -> /batch/index.html, which GitHub Pages serves directly
      images: { unoptimized: true },
    }
  : {};

export default nextConfig;
