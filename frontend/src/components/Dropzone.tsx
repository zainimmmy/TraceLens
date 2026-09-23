"use client";

import { useRef, useState } from "react";

interface Props {
  onFiles: (files: File[]) => void;
  multiple?: boolean;
  accept?: string;
  disabled?: boolean;
  title: string;
  hint: string;
  /** "compact" is the one-line bar shown above a report for analysing the next file. */
  variant?: "large" | "compact";
}

function UploadGlyph({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M2 7V2h5M17 2h5v5M22 17v5h-5M7 22H2v-5" />
      <path d="M12 16V8m0 0-3.5 3.5M12 8l3.5 3.5" strokeLinecap="square" />
    </svg>
  );
}

export default function Dropzone({ onFiles, multiple, accept = "image/jpeg,image/png,image/webp", disabled, title, hint, variant = "large" }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const compact = variant === "compact";

  const take = (list: FileList | null) => {
    if (!list || disabled) return;
    const files = Array.from(list);
    if (files.length) onFiles(multiple ? files : files.slice(0, 1));
  };

  const open = () => !disabled && input.current?.click();

  return (
    <div
      role="button"
      tabIndex={0}
      aria-disabled={disabled}
      aria-label={title}
      data-testid={compact ? "quick-upload" : "dropzone"}
      onClick={open}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && open()}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        take(e.dataTransfer.files);
      }}
      className={`panel group cursor-pointer outline-none transition-colors focus-visible:border-accent ${
        over ? "border-accent bg-accent-soft" : "hover:border-border-strong"
      } ${disabled ? "opacity-60 cursor-wait" : ""} ${
        compact ? "flex items-center gap-4 px-4 py-3" : "px-6 py-14 text-center"
      }`}
    >
      {compact ? (
        <>
          <span className="text-accent shrink-0">
            <UploadGlyph size={20} />
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-medium">{title}</span>
            <span className="block label text-[10px] mt-0.5 truncate">{hint}</span>
          </span>
          <span className="btn btn-ghost ml-auto shrink-0 py-2">Browse</span>
        </>
      ) : (
        <>
          <span className="mx-auto mb-5 w-14 h-14 grid place-items-center text-accent border border-border-strong group-hover:border-accent transition-colors">
            <UploadGlyph size={26} />
          </span>
          <p className="font-display text-lg font-semibold tracking-wide">{title}</p>
          <p className="label mt-2">{hint}</p>
        </>
      )}
      <input
        ref={input}
        type="file"
        accept={accept}
        multiple={multiple}
        className="sr-only"
        data-testid="file-input"
        onClick={(e) => e.stopPropagation()}
        onChange={(e) => {
          take(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
