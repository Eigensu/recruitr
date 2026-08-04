"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import ApplicationForm from "@/components/public/ApplicationForm";

/**
 * Unbranded application form.
 *
 * Works as-is when the deployment hosts a single agency. Multi-agency
 * deployments should link to /form/{domain}, which resolves the agency and
 * brands the page; ?brandId= remains accepted for links that carry a raw id.
 */
function PublicApplicationFormContent() {
  const brandId = useSearchParams().get("brandId");
  return <ApplicationForm brandId={brandId} />;
}

export default function PublicApplicationForm() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-shell flex items-center justify-center font-sans text-text-secondary text-sm">
          Loading...
        </div>
      }
    >
      <PublicApplicationFormContent />
    </Suspense>
  );
}
