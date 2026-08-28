import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * A KPI card. `delta` (optional) is a signed number rendered as a trend chip.
 * Keep animation minimal — a count-up on mount, nothing more.
 */
export default function StatCard({ label, value, delta, icon: Icon, hint }) {
  const up = typeof delta === "number" && delta >= 0;
  return (
    <Card className="lv-wash overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
        {Icon ? (
          <span className="flex size-7 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Icon className="size-4" />
          </span>
        ) : null}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold tracking-tight tabular-nums">{value}</div>
        <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
          {typeof delta === "number" && (
            <span
              className={cn(
                "inline-flex items-center gap-0.5 font-medium",
                up ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"
              )}
            >
              {up ? <ArrowUpRight className="size-3" /> : <ArrowDownRight className="size-3" />}
              {Math.abs(delta)}%
            </span>
          )}
          {hint}
        </div>
      </CardContent>
    </Card>
  );
}
