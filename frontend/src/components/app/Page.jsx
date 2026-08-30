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
  default: "max-w-[1400px]",
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
        <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">{title}</h2>
        {subtitle ? (
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{subtitle}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function SectionHeader({ children, action, className }) {
  return (
    <div className={cn("flex items-center justify-between gap-3", className)}>
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        {children}
      </h3>
      {action}
    </div>
  );
}
