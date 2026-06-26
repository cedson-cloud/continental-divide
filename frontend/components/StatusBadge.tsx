import { statusMeta } from "@/lib/format";

export function StatusBadge({ status }: { status: string }) {
  const meta = statusMeta(status);
  return <span className={`badge ${meta.tone}`}>{meta.label}</span>;
}
