"use client";

import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { FacetChip } from "./facet-chip";

export function ActiveFilterChips() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const yearMin = searchParams.get("year_min");
  const yearMax = searchParams.get("year_max");
  const scopeBuckets = searchParams.getAll("scope_bucket");
  const isOa = searchParams.get("is_oa");
  const tier = searchParams.get("tier");

  const chips: { label: string; remove: () => void }[] = [];

  function removeParam(key: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.delete(key);
    params.delete("page");
    router.push(`${pathname}?${params.toString()}`);
  }

  function removeScopeBucket(bucket: string) {
    const params = new URLSearchParams(searchParams.toString());
    const existing = params.getAll("scope_bucket").filter((b) => b !== bucket);
    params.delete("scope_bucket");
    existing.forEach((b) => params.append("scope_bucket", b));
    params.delete("page");
    router.push(`${pathname}?${params.toString()}`);
  }

  if (yearMin || yearMax) {
    const label =
      yearMin && yearMax
        ? `${yearMin}–${yearMax}`
        : yearMin
        ? `From ${yearMin}`
        : `To ${yearMax}`;
    chips.push({
      label,
      remove: () => {
        removeParam("year_min");
        removeParam("year_max");
      },
    });
  }

  scopeBuckets.forEach((b) => {
    chips.push({
      label: b.charAt(0).toUpperCase() + b.slice(1),
      remove: () => removeScopeBucket(b),
    });
  });

  if (tier) {
    chips.push({
      label: `Tier: ${tier}`,
      remove: () => removeParam("tier"),
    });
  }

  if (isOa === "true") {
    chips.push({ label: "Open access", remove: () => removeParam("is_oa") });
  } else if (isOa === "false") {
    chips.push({ label: "Closed access", remove: () => removeParam("is_oa") });
  }

  if (chips.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2" aria-label="Active filters">
      {chips.map(({ label, remove }) => (
        <FacetChip key={label} label={label} onRemove={remove} />
      ))}
    </div>
  );
}
