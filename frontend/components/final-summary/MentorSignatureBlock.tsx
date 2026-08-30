export function MentorSignatureBlock({
  mentorName,
}: {
  mentorName?: string | null;
}) {
  return (
    <section className="card space-y-3 p-5">
      <h2 className="section-title text-brand-dark">Mentor Signature</h2>
      <p className="text-sm text-ink">
        <span className="font-medium">Mentor Name:</span>{" "}
        <span className="text-ink-muted">{mentorName?.trim() || "—"}</span>
      </p>
      <div className="pt-2">
        <p className="text-sm font-medium text-ink">Signature:</p>
        <div className="mt-8 border-b border-ink/40 pb-1 text-ink-muted">
          ____________________________
        </div>
        <p className="mt-6 text-xs text-ink-muted">
          Printed signature placeholder for handwritten signing.
        </p>
      </div>
    </section>
  );
}
