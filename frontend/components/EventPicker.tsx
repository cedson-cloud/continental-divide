"use client";

import { useEffect, useId, useState } from "react";
import { getCatalog } from "@/lib/api";

// A datalist over the catalog's event names, labelled by category. Deliberately
// not a strict select: a requester may know about an event the catalog does not
// have yet, so any typed value is accepted verbatim and the engine judges it.
export function EventPicker({
  value,
  onChange,
  placeholder = "e.g. Order Completed",
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
}) {
  const listId = useId();
  const [options, setOptions] = useState<{ name: string; category: string }[]>([]);

  useEffect(() => {
    // If the catalog cannot be fetched the picker degrades to a plain text
    // input, which is exactly the field it replaced.
    getCatalog()
      .then((catalog) =>
        setOptions(
          catalog.events.map((e) => ({ name: e.name, category: e.category })),
        ),
      )
      .catch(() => setOptions([]));
  }, []);

  return (
    <>
      <input
        type="text"
        list={listId}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      />
      <datalist id={listId}>
        {options.map((o, i) => (
          <option key={`${o.name}:${i}`} value={o.name} label={o.category} />
        ))}
      </datalist>
    </>
  );
}
