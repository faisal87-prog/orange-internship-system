"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

const STATUS_MESSAGES = [
  "Preparing program context...",
  "Building the AI roadmap prompt...",
  "Generating weeks and tasks...",
  "Finalizing your draft roadmap...",
];

export function RoadmapGenerationLoader() {
  const [statusIndex, setStatusIndex] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setStatusIndex((current) => (current + 1) % STATUS_MESSAGES.length);
    }, 4500);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div
      className="card mx-auto flex min-h-[22rem] max-w-2xl flex-col items-center justify-center px-6 py-12 text-center"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="relative flex h-28 w-28 items-center justify-center sm:h-32 sm:w-32">
        <div
          className="absolute inset-0 rounded-full border-2 border-brand/25 border-t-brand animate-roadmap-ring-spin"
          aria-hidden
        />
        <div className="relative flex h-20 w-20 items-center justify-center overflow-hidden rounded-full bg-white shadow-soft sm:h-24 sm:w-24 animate-roadmap-logo-breathe">
          <Image
            src="/branding/orange-logo.jpeg"
            alt="Orange"
            width={96}
            height={96}
            className="h-14 w-14 object-contain sm:h-16 sm:w-16"
            priority
          />
        </div>
      </div>

      <h2 className="mt-8 text-xl font-semibold tracking-tight text-ink sm:text-2xl">
        Generating your internship roadmap...
      </h2>
      <p className="mt-3 max-w-md text-sm text-ink-muted sm:text-base">
        AI is analyzing the program, learning goals, skills, and internship structure. This may
        take a moment.
      </p>
      <p className="mt-5 text-sm font-medium text-brand-dark">{STATUS_MESSAGES[statusIndex]}</p>
    </div>
  );
}
