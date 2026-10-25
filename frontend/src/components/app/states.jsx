import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { NoResultsIllustration } from "@/components/app/Illustrations";

/**
 * Designed empty / loading / error states shared across screens.
 * `illustration` is a node (inline SVG) shown above the title.
 */
export function EmptyState({ icon: Icon, illustration, title, description, action, secondary, className }) {
  const btn = (a, variant) =>
    a?.to ? (
      <Button asChild size="sm" variant={variant}>
        <Link to={a.to}>{a.label}</Link>
      </Button>
    ) : a?.onClick ? (
      <Button size="sm" variant={variant} onClick={a.onClick}>
        {a.label}
      </Button>
    ) : null;
  return (
    <div
      className={cn(
        "lv-r-hero flex flex-col items-center gap-3 border border-dashed border-[#C7D6F0] bg-white/70 px-6 py-12 text-center",
        className
      )}
    >
      {illustration ? (
        illustration
      ) : Icon ? (
        <div className="flex size-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Icon className="size-5" />
        </div>
      ) : null}
      <p className="t-h2">{title}</p>
      {description ? <p className="t-body max-w-sm text-muted-foreground">{description}</p> : null}
      {action || secondary ? (
        <div className="mt-1 flex flex-wrap items-center justify-center gap-2">
          {btn(action, "default")}
          {btn(secondary, "outline")}
        </div>
      ) : null}
    </div>
  );
}

export function NoResults({ query, onClear }) {
  return (
    <EmptyState
      illustration={<NoResultsIllustration />}
      title="Nothing matches that"
      description={query ? `No results for “${query}”. Try a different word or clear the filters.` : "Try clearing the filters."}
      action={onClear ? { label: "Clear filters", onClick: onClear } : undefined}
    />
  );
}

export function LoadingGrid({ count = 6, className, itemClassName = "aspect-[4/3]" }) {
  return (
    <div className={cn("grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="lv-surface overflow-hidden">
          <div className={cn("lv-skel rounded-none", itemClassName)} />
          <div className="space-y-2 p-3">
            <div className="lv-skel h-3.5 w-3/4" />
            <div className="lv-skel h-3 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function ErrorNote({ error, className }) {
  if (!error) return null;
  return (
    <p className={cn("rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive", className)}>
      {typeof error === "string" ? error : error.message || "Something went wrong."}
    </p>
  );
}
