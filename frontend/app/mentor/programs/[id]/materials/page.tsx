"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { ResourceList } from "@/components/resources/ResourceList";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { PageHeader } from "@/components/ui/PageHeader";
import { getErrorMessage } from "@/lib/api/errors";
import {
  createProgramMaterial,
  deleteProgramMaterial,
  getProgram,
  listProgramMaterials,
} from "@/lib/api/programs";
import type { InternshipProgram, ReferenceMaterial } from "@/types";

const ALLOWED = "PDF, DOC, DOCX, PPT, PPTX, PNG, JPG, JPEG, TXT, CSV, ZIP · max 20 MB";

export default function ProgramMaterialsPage() {
  const params = useParams<{ id: string }>();
  const [program, setProgram] = useState<InternshipProgram | null>(null);
  const [items, setItems] = useState<ReferenceMaterial[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [prog, materials] = await Promise.all([
        getProgram(params.id),
        listProgramMaterials(params.id),
      ]);
      setProgram(prog);
      setItems(materials);
    } catch (err) {
      setError(getErrorMessage(err, "Could not load materials."));
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!program) return;
    const formEl = e.currentTarget;
    const form = new FormData(formEl);
    const title = String(form.get("title") || "").trim();
    const externalLink = String(form.get("externalLink") || "").trim();
    const fileField = form.get("file");
    const file = fileField instanceof File && fileField.name ? fileField : null;
    if (!title) {
      setMessage("Title is required.");
      return;
    }
    if (!file && !externalLink) {
      setMessage("Please provide a file or an external link.");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const created = await createProgramMaterial({
        program: Number(program.id),
        title,
        external_url: externalLink || undefined,
        file,
      });
      setItems((prev) => [...prev, created]);
      setMessage("Reference material added.");
      formEl.reset();
    } catch (err) {
      setMessage(getErrorMessage(err, "Could not add material."));
    } finally {
      setBusy(false);
    }
  }

  async function onRemove(id: string) {
    setBusy(true);
    setMessage("");
    try {
      await deleteProgramMaterial(id);
      setItems((prev) => prev.filter((item) => item.id !== id));
      setMessage("Material removed.");
    } catch (err) {
      setMessage(getErrorMessage(err, "Could not remove material."));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingState label="Loading materials…" />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!program) return <p>Program not found.</p>;

  return (
    <div>
      <PageHeader
        title="Reference materials"
        description={`Optional materials for AI roadmap context. Allowed types: ${ALLOWED}.`}
        actions={
          <Link href={`/mentor/programs/${program.id}`} className="btn-secondary">
            Back to program
          </Link>
        }
      />

      <form onSubmit={onSubmit} className="card mb-6 grid gap-4 p-5 md:grid-cols-2">
        <div className="md:col-span-2">
          <label className="label" htmlFor="title">Title</label>
          <input id="title" name="title" required className="input" />
        </div>
        <div>
          <label className="label" htmlFor="file">File upload</label>
          <input id="file" name="file" type="file" className="input" />
        </div>
        <div>
          <label className="label" htmlFor="externalLink">External link (optional)</label>
          <input id="externalLink" name="externalLink" type="url" className="input" placeholder="https://" />
        </div>
        <div className="md:col-span-2">
          <button type="submit" className="btn-primary" disabled={busy}>
            Add material
          </button>
          {message ? <p className="mt-2 text-sm text-emerald-700">{message}</p> : null}
        </div>
      </form>

      {items.length === 0 ? (
        <EmptyState
          title="No reference materials"
          description="Add PDFs, documents, presentations, or links to support roadmap generation."
        />
      ) : (
        <div className="card p-5">
          <ResourceList
            resources={items}
            onRemove={busy ? undefined : onRemove}
          />
        </div>
      )}
    </div>
  );
}
