import { AuditEntry } from "@/lib/api";
import { requestProgress } from "@/lib/progress";
import { Icon } from "@/components/icons";

export function RequestProgress({
  status,
  auditLog,
}: {
  status: string;
  auditLog: AuditEntry[];
}) {
  const steps = requestProgress(status, auditLog);
  return (
    <ol className="progress" aria-label="Request progress">
      {steps.map((step) => (
        <li
          key={step.label}
          className={`progress-step${step.done ? " done" : ""}${
            step.current ? " current" : ""
          } ${step.tone}`}
          aria-current={step.current ? "step" : undefined}
        >
          <span className="progress-dot" aria-hidden="true">
            {step.done && <Icon name="check" size={13} />}
          </span>
          {step.label}
          {step.done && !step.current && <span className="visually-hidden"> (done)</span>}
          {!step.done && !step.current && (
            <span className="visually-hidden"> (not reached)</span>
          )}
        </li>
      ))}
    </ol>
  );
}
