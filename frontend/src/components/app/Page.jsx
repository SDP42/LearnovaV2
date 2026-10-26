import { cn } from "@/lib/utils";

/**
 * Shared page primitives so every authenticated screen uses one container
 * width, one spacing rhythm and one header hierarchy.
 *
 *   <PageContainer>
 *     <PageHeader title="Presentations" subtitle="…" actions={<Button/>} />
 *     <SectionHeader>Recent</SectionHeader>
 *     …
 *   </PageContainer>
 *
 * width:  "default" → dashboards / grids / tables (max-w-[1400px])
 *         "prose"   → forms & reading views (max-w-3xl)
 *         "narrow"  → focused single-column flows (max-w-xl)
 */
const WIDTHS = {
  default: "max-w-full",
  prose: "max-w-3xl",
  narrow: "max-w-xl",
};

export function PageContainer({ width = "default", className, children }) {
  return (
    <div className={cn("mx-auto flex w-full flex-col gap-6", WIDTHS[width] || WIDTHS.default, className)}>
      {children}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions, className }) {
  return (
    <div className={cn("flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="min-w-0">
        <h1 className="t-h1">{title}</h1>
        {subtitle ? (
          <p className="t-body mt-1 max-w-2xl text-muted-foreground">{subtitle}</p>
        ) : null}
      </div>
      {actions ? <div className="flex w-full shrink-0 items-center gap-2 sm:w-auto">{actions}</div> : null}
    </div>
  );
}

export function SectionHeader({ children, action, className }) {
  return (
    <div className={cn("flex items-center justify-between gap-3", className)}>
      <h2 className="t-h2">
        {children}
      </h2>
      {action}
    </div>
  );
}
