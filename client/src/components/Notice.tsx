import type { ReactNode } from "react";

export function Notice({
  children,
  kind = "info",
  action,
}: {
  children: ReactNode;
  kind?: "info" | "error";
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div
      className={`notice notice-${kind}`}
      role={kind === "error" ? "alert" : "status"}
    >
      <span>{children}</span>
      {action && (
        <button type="button" onClick={action.onClick}>
          {action.label}
        </button>
      )}
    </div>
  );
}
