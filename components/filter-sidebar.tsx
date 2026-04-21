"use client";

import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useCallback } from "react";
import { X } from "lucide-react";

const SCOPE_BUCKETS = [
  { value: "tourism", label: "Tourism" },
  { value: "hospitality", label: "Hospitality" },
  { value: "events", label: "Events" },
  { value: "leisure", label: "Leisure" },
  { value: "destination", label: "Destination" },
  { value: "mixed", label: "Mixed" },
] as const;

export function FilterSidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const q = searchParams.get("q") ?? "";
  const yearMin = searchParams.get("year_min") ?? "";
  const yearMax = searchParams.get("year_max") ?? "";
  const scopeBuckets = searchParams.getAll("scope_bucket");
  const isOa = searchParams.get("is_oa") ?? "";
  const tier = searchParams.get("tier") ?? "";
  const sort = searchParams.get("sort") ?? "";

  const buildUrl = useCallback(
    (updates: Record<string, string | string[] | null>) => {
      const params = new URLSearchParams();
      if (q) params.set("q", q);

      // Apply existing values, overridden by updates
      const effective: Record<string, string | string[] | null> = {
        year_min: yearMin || null,
        year_max: yearMax || null,
        scope_bucket: scopeBuckets.length ? scopeBuckets : null,
        is_oa: isOa || null,
        tier: tier || null,
        sort: sort || null,
        ...updates,
      };

      for (const [key, val] of Object.entries(effective)) {
        if (!val) continue;
        if (Array.isArray(val)) {
          val.forEach((v) => params.append(key, v));
        } else {
          params.set(key, val);
        }
      }
      // Always reset to page 1 on filter change
      params.delete("page");
      return `${pathname}?${params.toString()}`;
    },
    [q, yearMin, yearMax, scopeBuckets, isOa, tier, sort, pathname]
  );

  const hasFilters =
    yearMin || yearMax || scopeBuckets.length || isOa || tier;

  function clearAll() {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    router.push(`${pathname}?${params.toString()}`);
  }

  function toggleScopeBucket(bucket: string) {
    const next = scopeBuckets.includes(bucket)
      ? scopeBuckets.filter((b) => b !== bucket)
      : [...scopeBuckets, bucket];
    router.push(buildUrl({ scope_bucket: next.length ? next : null }));
  }

  function handleYearBlur() {
    const minEl = document.getElementById("year-min") as HTMLInputElement | null;
    const maxEl = document.getElementById("year-max") as HTMLInputElement | null;
    const newMin = minEl?.value.trim() || null;
    const newMax = maxEl?.value.trim() || null;
    router.push(buildUrl({ year_min: newMin, year_max: newMax }));
  }

  return (
    <aside aria-label="Filters" className="w-full space-y-6 text-sm">
      {/* Sort */}
      <div>
        <label
          htmlFor="sort-select"
          className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-2"
        >
          Sort
        </label>
        <select
          id="sort-select"
          value={sort}
          onChange={(e) =>
            router.push(buildUrl({ sort: e.target.value || null }))
          }
          className="w-full rounded border border-surface-border bg-surface-raised text-ink text-sm px-3 py-1.5 focus:outline-none focus:border-accent"
        >
          <option value="">Relevance</option>
          <option value="year_desc">Newest first</option>
          <option value="year_asc">Oldest first</option>
          <option value="citations_desc">Most cited</option>
        </select>
      </div>

      {/* Year range */}
      <div>
        <p className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-2">
          Year
        </p>
        <div className="flex items-center gap-2">
          <input
            id="year-min"
            type="number"
            placeholder="From"
            defaultValue={yearMin}
            min={1960}
            max={2030}
            onBlur={handleYearBlur}
            className="w-full rounded border border-surface-border bg-surface-raised text-ink text-sm px-2 py-1.5 focus:outline-none focus:border-accent"
          />
          <span className="text-ink-subtle text-xs">–</span>
          <input
            id="year-max"
            type="number"
            placeholder="To"
            defaultValue={yearMax}
            min={1960}
            max={2030}
            onBlur={handleYearBlur}
            className="w-full rounded border border-surface-border bg-surface-raised text-ink text-sm px-2 py-1.5 focus:outline-none focus:border-accent"
          />
        </div>
      </div>

      {/* Scope bucket */}
      <div>
        <p className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-2">
          Scope
        </p>
        <ul className="space-y-1 list-none m-0 p-0">
          {SCOPE_BUCKETS.map(({ value, label }) => {
            const checked = scopeBuckets.includes(value);
            return (
              <li key={value}>
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleScopeBucket(value)}
                    className="accent-accent"
                  />
                  <span
                    className={`text-sm transition-colors ${
                      checked ? "text-ink" : "text-ink-muted group-hover:text-ink"
                    }`}
                  >
                    {label}
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      </div>

      {/* Tier */}
      <div>
        <p className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-2">
          Tier
        </p>
        <ul className="space-y-1 list-none m-0 p-0">
          {[
            { value: "", label: "All" },
            { value: "core", label: "Core" },
            { value: "extended", label: "Extended" },
          ].map(({ value, label }) => (
            <li key={value}>
              <label className="flex items-center gap-2 cursor-pointer group">
                <input
                  type="radio"
                  name="tier"
                  value={value}
                  checked={tier === value}
                  onChange={() =>
                    router.push(buildUrl({ tier: value || null }))
                  }
                  className="accent-accent"
                />
                <span className="text-sm text-ink-muted group-hover:text-ink transition-colors">
                  {label}
                </span>
              </label>
            </li>
          ))}
        </ul>
      </div>

      {/* Open access */}
      <div>
        <p className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-2">
          Open access
        </p>
        <ul className="space-y-1 list-none m-0 p-0">
          {[
            { value: "", label: "All" },
            { value: "true", label: "Open access only" },
            { value: "false", label: "Closed access only" },
          ].map(({ value, label }) => (
            <li key={value}>
              <label className="flex items-center gap-2 cursor-pointer group">
                <input
                  type="radio"
                  name="is_oa"
                  value={value}
                  checked={isOa === value}
                  onChange={() =>
                    router.push(buildUrl({ is_oa: value || null }))
                  }
                  className="accent-accent"
                />
                <span className="text-sm text-ink-muted group-hover:text-ink transition-colors">
                  {label}
                </span>
              </label>
            </li>
          ))}
        </ul>
      </div>

      {/* Clear */}
      {hasFilters && (
        <button
          onClick={clearAll}
          className="flex items-center gap-1.5 text-xs text-ink-muted hover:text-accent transition-colors"
        >
          <X size={13} />
          Clear all filters
        </button>
      )}
    </aside>
  );
}
