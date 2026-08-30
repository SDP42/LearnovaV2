import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/**
 * Designed empty / loading / error states shared across screens.
 */
export function EmptyState({ icon: Icon, title, description, action, className }) {
  return (
    <Card className={cn("border-dashed", className)}>
      <CardContent className="flex flex-col items-center gap-3 px-6 py-14 text-center">
        {Icon ? (
          <div className="flex size-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Icon className="size-5" />
          </div>
        ) : null}
        <p className="text-sm font-medium">{title}</p>
        {description ? (
          <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
        ) : null}
        {action?.to ? (
          <Button asChild size="sm" className="mt-1">
            <Link to={action.to}>{action.label}</Link>
          </Button>
        ) : action?.onClick ? (
          <Button size="sm" className="mt-1" onClick={action.onClick}>
            {action.label}
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function LoadingGrid({ count = 6, className, itemClassName = "h-40 rounded-xl" }) {
  return (
    <div className={cn("grid gap-4 sm:grid-cols-2 lg:grid-cols-3", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className={itemClassName} />
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
