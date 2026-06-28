import Link from "next/link";

import { EditorialContainer } from "@/components/app-shell";
import { secondaryCtaClass } from "@/lib/cta-classes";

export const metadata = {
  title: "Dev gallery — Roast My Startup",
};

export default function DevGalleryPage() {
  return (
    <EditorialContainer className="py-12 md:py-16">
      <div className="col-span-12">
        <p className="font-sans text-sm font-semibold uppercase tracking-widest text-heat-ink">
          Phase 0
        </p>
        <h1 className="mt-2 font-serif text-title font-semibold text-ink md:text-display-md">
          Component gallery
        </h1>
        <p className="mt-4 max-w-prose font-sans text-ink-muted">
          Empty for now. Phase 1 will render every primitive and signature component
          here in all states — loading, empty, error, success.
        </p>
        <Link href="/" className={`mt-8 ${secondaryCtaClass}`}>
          Back home
        </Link>
      </div>
    </EditorialContainer>
  );
}
