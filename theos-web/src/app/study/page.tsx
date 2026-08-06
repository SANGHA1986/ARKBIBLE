"use client";

import { Suspense } from "react";
import StudyInner from "./StudyInner";

export default function StudyPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-6xl mx-auto px-4 py-16 text-ark-grey text-sm">
          Loading lexicon…
        </div>
      }
    >
      <div className="max-w-6xl mx-auto px-4">
        <StudyInner />
      </div>
    </Suspense>
  );
}
