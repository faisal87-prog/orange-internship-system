"use client";

import { FormEvent, useState } from "react";
import { ResourceList } from "@/components/resources/ResourceList";
import { getErrorMessage } from "@/lib/api/errors";
import { inferResourceKind, MOCK_PDF_HREF } from "@/lib/resources";
import type { LearningResource } from "@/types";

/** Local pending resource that still holds the File for later upload. */
export type PendingLearningResource = LearningResource & { file?: File };

export function ResourceManager({
  resources,
  onChange,
  title = "Task resources",
  onAddRequest,
  onRemoveRequest,
}: {
  resources: PendingLearningResource[];
  onChange: (next: PendingLearningResource[]) => void;
  title?: string;
  onAddRequest?: (input: {
    title: string;
    externalLink: string;
    files: File[];
  }) => Promise<LearningResource[]>;
  onRemoveRequest?: (id: string) => Promise<void>;
}) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function onAdd(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formEl = e.currentTarget;
    const form = new FormData(formEl);
    const resourceTitle = String(form.get("title") || "").trim();
    const externalLink = String(form.get("externalLink") || "").trim();
    const files = form
      .getAll("files")
      .filter((f): f is File => f instanceof File && Boolean(f.name));

    if (!resourceTitle) {
      setMessage("Resource title is required.");
      return;
    }
    if (files.length === 0 && !externalLink) {
      setMessage("Please provide a file or an external link.");
      return;
    }

    if (onAddRequest) {
      setBusy(true);
      try {
        const created = await onAddRequest({
          title: resourceTitle,
          externalLink,
          files,
        });
        onChange([...resources, ...created]);
        setMessage("Resource(s) added.");
        formEl.reset();
      } catch (error) {
        setMessage(getErrorMessage(error, "Could not add resource."));
      } finally {
        setBusy(false);
      }
      return;
    }

    const next: PendingLearningResource[] = [...resources];

    if (files.length) {
      files.forEach((file, index) => {
        next.push({
          id: `res-local-${Date.now()}-${index}`,
          title: resourceTitle || file.name,
          fileName: file.name,
          kind: inferResourceKind(file.name),
          href: MOCK_PDF_HREF,
          externalUrl: externalLink || undefined,
          file,
        });
      });
    } else {
      next.push({
        id: `res-local-${Date.now()}`,
        title: resourceTitle || externalLink,
        kind: "LINK",
        href: externalLink,
        externalUrl: externalLink,
      });
    }

    onChange(next);
    setMessage("Resources staged. They will upload when you save.");
    formEl.reset();
  }

  async function handleRemove(id: string) {
    if (onRemoveRequest) {
      setBusy(true);
      try {
        await onRemoveRequest(id);
        onChange(resources.filter((r) => r.id !== id));
        setMessage("Resource removed.");
      } catch (error) {
        setMessage(getErrorMessage(error, "Could not remove resource."));
      } finally {
        setBusy(false);
      }
      return;
    }
    onChange(resources.filter((r) => r.id !== id));
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="section-title">{title}</h2>
        <p className="mt-1 text-sm text-ink-muted">
          Upload PDFs, Word, PowerPoint, images, ZIP, or add external links. Max 20 MB per
          file.
        </p>
      </div>

      <ResourceList
        resources={resources}
        emptyLabel="No resources yet. Add files or links below."
        onRemove={busy ? undefined : handleRemove}
      />

      <form onSubmit={onAdd} className="grid gap-3 rounded-xl border border-dashed border-line p-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <label className="label" htmlFor="resource-title">
            Resource title
          </label>
          <input id="resource-title" name="title" className="input" placeholder="e.g. UI Guidelines" />
        </div>
        <div>
          <label className="label" htmlFor="resource-files">
            Upload files (multiple)
          </label>
          <input
            id="resource-files"
            name="files"
            type="file"
            multiple
            className="input"
            accept=".pdf,.doc,.docx,.ppt,.pptx,.png,.jpg,.jpeg,.zip,.txt,.csv"
          />
        </div>
        <div>
          <label className="label" htmlFor="resource-link">
            External link
          </label>
          <input
            id="resource-link"
            name="externalLink"
            type="url"
            className="input"
            placeholder="https://"
          />
        </div>
        <div className="md:col-span-2 flex flex-wrap items-center gap-3">
          <button type="submit" className="btn-secondary" disabled={busy}>
            Add resources
          </button>
          {message ? <p className="text-sm text-emerald-700">{message}</p> : null}
        </div>
      </form>
    </section>
  );
}
