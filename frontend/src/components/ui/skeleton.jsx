import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }) {
  return (
    <div className={cn("animate-pulse rounded-lg bg-[#EFE1D4]", className)} {...props} />
  );
}

export { Skeleton };
