import type { LearningResource, ResourceKind } from "@/types";

export function inferResourceKind(
  fileName?: string,
  href?: string,
): ResourceKind {
  const value = `${fileName ?? ""} ${href ?? ""}`.toLowerCase();
  if (value.startsWith("http://") || value.startsWith("https://")) {
    if (!fileName) return "LINK";
  }
  if (value.includes(".pdf")) return "PDF";
  if (value.includes(".doc")) return "DOC";
  if (value.includes(".ppt")) return "PPT";
  if (
    value.includes(".png") ||
    value.includes(".jpg") ||
    value.includes(".jpeg") ||
    value.includes(".gif") ||
    value.includes(".webp")
  ) {
    return "IMAGE";
  }
  if (value.includes(".zip")) return "ZIP";
  if (href?.startsWith("http")) return "LINK";
  return "OTHER";
}

export function resourceIcon(kind: ResourceKind): string {
  switch (kind) {
    case "PDF":
      return "📄";
    case "DOC":
      return "📝";
    case "PPT":
      return "📊";
    case "IMAGE":
      return "🖼️";
    case "ZIP":
      return "🗜️";
    case "LINK":
      return "🔗";
    default:
      return "📎";
  }
}

export function resourceKindLabel(kind: ResourceKind): string {
  switch (kind) {
    case "PDF":
      return "PDF";
    case "DOC":
      return "Word";
    case "PPT":
      return "PowerPoint";
    case "IMAGE":
      return "Image";
    case "ZIP":
      return "ZIP";
    case "LINK":
      return "Link";
    default:
      return "Document";
  }
}

export function isExternalHref(href: string) {
  return href.startsWith("http://") || href.startsWith("https://");
}

/** Shared mock PDF used for frontend-only downloads and document opens. */
export const MOCK_PDF_HREF = "/mock/sample-document.pdf";

export function toLearningResource(input: {
  id: string;
  title: string;
  fileName?: string;
  href?: string;
  externalLink?: string;
  externalUrl?: string;
}): LearningResource {
  const externalUrl = input.externalUrl || input.externalLink || "";
  const href = input.href || externalUrl || MOCK_PDF_HREF;
  const kind = inferResourceKind(input.fileName, href);
  return {
    id: input.id,
    title: input.title,
    kind,
    fileName: input.fileName,
    href,
    externalUrl: externalUrl || undefined,
  };
}
