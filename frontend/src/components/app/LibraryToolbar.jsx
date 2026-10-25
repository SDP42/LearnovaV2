import { LayoutGrid, List, Search, X } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

/**
 * Shared library toolbar: search, filter chips, sort select, grid/list toggle.
 * Any prop group may be omitted to hide that control.
 */
export default function LibraryToolbar({
  query,
  onQuery,
  placeholder = "Search…",
  chips,
  chip,
  onChip,
  sorts,
  sort,
  onSort,
  view,
  onView,
  children,
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        {onQuery ? (
          <div className="relative min-w-0 flex-1 sm:max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#8190AD]" />
            <input
              value={query}
              onChange={(e) => onQuery(e.target.value)}
              placeholder={placeholder}
              aria-label={placeholder}
              className="h-9 w-full rounded-full border border-[#DEE7F5] bg-white pl-9 pr-8 text-[14px] outline-none transition placeholder:text-[#8190AD] focus:border-[#9DBBF5] focus:shadow-[0_0_0_3px_rgb(37_99_235/0.10)]"
            />
            {query ? (
              <button onClick={() => onQuery("")} aria-label="Clear search" className="absolute right-2 top-1/2 grid size-5 -translate-y-1/2 place-items-center rounded-full text-[#8190AD] hover:bg-[#EEF3FB]">
                <X className="size-3.5" />
              </button>
            ) : null}
          </div>
        ) : null}
        <div className="ml-auto flex items-center gap-2">
          {children}
          {sorts ? (
            <Select value={sort} onValueChange={onSort}>
              <SelectTrigger aria-label="Sort" className="h-9 w-auto gap-1.5 rounded-full border-[#DEE7F5] bg-white px-3 text-[13px] font-medium shadow-none">
                <span className="text-[#8190AD]">Sort:</span>
                <SelectValue />
              </SelectTrigger>
              <SelectContent align="end">
                {sorts.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : null}
          {onView ? (
            <div className="inline-flex rounded-full border border-[#DEE7F5] bg-white p-0.5" role="group" aria-label="View">
              {[
                ["grid", LayoutGrid, "Grid view"],
                ["list", List, "List view"],
              ].map(([v, Icon, label]) => (
                <button
                  key={v}
                  onClick={() => onView(v)}
                  aria-label={label}
                  aria-pressed={view === v}
                  className={cn(
                    "grid size-8 place-items-center rounded-full text-[#6A7A9B] transition",
                    view === v && "bg-[#E6EEFD] text-[#1D4ED8]"
                  )}
                >
                  <Icon className="size-4" />
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>
      {chips ? (
        <div className="lv-no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1">
          {chips.map((c) => (
            <button
              key={c.id}
              onClick={() => onChip(c.id)}
              aria-pressed={chip === c.id}
              className={cn(
                "shrink-0 rounded-full border px-3.5 py-1 text-[13px] font-medium transition",
                chip === c.id
                  ? "border-[#2563EB] bg-[#E6EEFD] text-[#1D4ED8]"
                  : "border-[#DEE7F5] bg-white text-[#4A5C80] hover:border-[#B9CBEA]"
              )}
            >
              {c.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
