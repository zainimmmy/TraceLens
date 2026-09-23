"use client";

import { useRef, useState } from "react";

interface Props {
  onFiles: (files: File[]) => void;
  multiple?: boolean;
  accept?: string;
  disabled?: boolean;
  title: string;
  hint: string;
}

export default function Dropzone({ onFiles, multiple, accept = "image/jpeg,image/png,image/webp", disabled, title, hint }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const take = (list: FileList | null) => {
    if (!list || disabled) return;
    const files = Array.from(list);
    if (files.length) onFiles(multiple ? files : files.slice(0, 1));
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-disabled={disabled}
      data-testid="dropzone"
      onClick={() => !disabled && input.current?.click()}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && !disabled && input.current?.click()}
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
      className={`card border-2 border-dashed px-6 py-12 text-center cursor-pointer transition-colors outline-none focus-visible:border-accent ${
        over ? "border-accent bg-accent-soft" : "hover:border-accent/60"
      } ${disabled ? "opacity-60 cursor-wait" : ""}`}
    >
      <div className="mx-auto mb-4 w-12 h-12 rounded-full bg-accent-soft text-accent grid place-items-center">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M12 16V4m0 0-4 4m4-4 4 4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" />
        </svg>
      </div>
      <p className="font-medium">{title}</p>
      <p className="text-sm text-muted mt-1">{hint}</p>
      <input
        ref={input}
        type="file"
        accept={accept}
        multiple={multiple}
        className="sr-only"
        data-testid="file-input"
        onChange={(e) => {
          take(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
