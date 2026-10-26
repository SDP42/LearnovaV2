import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { CountUp } from "@/components/app/motion";

/**
 * A KPI card. `delta` (optional) is a signed number rendered as a trend chip.
 * Keep animation minimal — a count-up on mount, nothing more.
 */
export default function StatCard({ label, value, delta, icon: Icon, hint }) {
  const up = typeof delta === "number" && delta >= 0;
  return (
    <Card className="lv-lift h-full overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-2 sm:p-6 sm:pb-2">
        <CardTitle className="t-meta !font-medium">{label}</CardTitle>
        {Icon ? (
          <span className="flex size-8 items-center justify-center rounded-lg bg-[#FCE5D6] text-[#8F3A18]">
            <Icon className="size-4" />
          </span>
        ) : null}
      </CardHeader>
      <CardContent className="p-4 pt-0 sm:p-6 sm:pt-0">
        <div className="font-[Bricolage_Grotesque] text-[28px] font-bold leading-8 tracking-tight tabular-nums text-[#402B25]">
          <CountUp value={typeof value === "string" && /^\d+$/.test(value) ? Number(value) : value} />
        </div>
        <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
          {typeof delta === "number" && (
            <span
              className={cn(
                "inline-flex items-center gap-0.5 font-medium",
                up ? "text-[#3F6B47]" : "text-[#A53125]"
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
