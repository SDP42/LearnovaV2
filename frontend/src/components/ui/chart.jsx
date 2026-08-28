import * as React from "react";
import * as RechartsPrimitive from "recharts";
import { cn } from "@/lib/utils";

const ChartContext = React.createContext(null);

function useChart() {
  const ctx = React.useContext(ChartContext);
  if (!ctx) throw new Error("useChart must be used within a <ChartContainer />");
  return ctx;
}

/**
 * Minimal shadcn-style chart wrapper. `config` maps a data key to
 * { label, color }; colors are exposed as CSS vars (--color-<key>) so Recharts
 * series can reference them.
 */
const ChartContainer = React.forwardRef(
  ({ id, className, children, config, ...props }, ref) => {
    const uid = React.useId();
    const chartId = `chart-${id || uid.replace(/:/g, "")}`;
    const style = Object.fromEntries(
      Object.entries(config || {})
        .filter(([, v]) => v.color)
        .map(([k, v]) => [`--color-${k}`, v.color])
    );

    return (
      <ChartContext.Provider value={{ config }}>
        <div
          ref={ref}
          data-chart={chartId}
          style={style}
          className={cn(
            "flex aspect-video justify-center text-xs [&_.recharts-cartesian-axis-tick_text]:fill-muted-foreground [&_.recharts-cartesian-grid_line]:stroke-border/50 [&_.recharts-surface]:outline-none",
            className
          )}
          {...props}
        >
          <RechartsPrimitive.ResponsiveContainer>
            {children}
          </RechartsPrimitive.ResponsiveContainer>
        </div>
      </ChartContext.Provider>
    );
  }
);
ChartContainer.displayName = "ChartContainer";

function ChartTooltipContent({ active, payload, label }) {
  const { config } = useChart();
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-popover px-2.5 py-1.5 text-xs shadow-md">
      {label != null ? <p className="mb-1 font-medium">{label}</p> : null}
      {payload.map((item) => {
        const key = item.dataKey ?? item.name;
        const c = config?.[key];
        return (
          <div key={key} className="flex items-center gap-2">
            <span
              className="size-2 rounded-[2px]"
              style={{ background: c?.color ?? item.color }}
            />
            <span className="text-muted-foreground">{c?.label ?? key}</span>
            <span className="ml-auto font-medium tabular-nums">{item.value}</span>
          </div>
        );
      })}
    </div>
  );
}

const ChartTooltip = RechartsPrimitive.Tooltip;

export { ChartContainer, ChartTooltip, ChartTooltipContent, useChart };
