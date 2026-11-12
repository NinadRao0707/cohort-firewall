"use client";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

/** A filter chip that opens one small editor. Desktop: a popover under the chip. Phone: a bottom sheet.
 *  Escape or a click outside closes it, and focus returns to the chip. */
export function ChipPopover({ label, title, children, onRemove, variant = "chip", width = 320 }: {
  label: ReactNode; title: string; children: (close: () => void) => ReactNode;
  onRemove?: () => void; variant?: "chip" | "add" | "plain"; width?: number;
}) {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const btn = useRef<HTMLButtonElement>(null);
  const id = useId();
  const close = () => { setOpen(false); btn.current?.focus(); };
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    const onDown = (e: MouseEvent) => { if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onDown); };
  }, [open]);
  return (
    <div className="pop-wrap" ref={wrap}>
      <span className={`chip-btn ${variant}`} data-open={open || undefined}>
        <button ref={btn} type="button" aria-haspopup="dialog" aria-expanded={open} aria-controls={id}
                onClick={() => setOpen((o) => !o)}>{label}</button>
        {onRemove && <button type="button" className="chip-x" aria-label={`Remove ${title}`} onClick={onRemove}>×</button>}
      </span>
      {open && (
        <>
          <div className="sheet-backdrop" onClick={() => setOpen(false)} />
          <div className="pop" id={id} role="dialog" aria-label={title} style={{ ["--pop-w" as string]: `${width}px` }}>
            <div className="pop-head"><strong>{title}</strong>
              <button type="button" className="pop-close" aria-label="Close" onClick={close}>×</button></div>
            <div className="pop-body">{children(close)}</div>
          </div>
        </>
      )}
    </div>
  );
}

/** Searchable checklist for long lists (predictors, fairness attributes). */
export function CheckList({ items, selected, onToggle, search = true, empty = "No matches." }: {
  items: { value: string; label: string; hint?: string }[]; selected: string[];
  onToggle: (v: string) => void; search?: boolean; empty?: string;
}) {
  const [q, setQ] = useState("");
  // Ticked items first (sorted once on open, so rows don't jump while ticking).
  const [order] = useState(() => [...items].sort((a, b) => Number(selected.includes(b.value)) - Number(selected.includes(a.value))));
  const base = order.length === items.length ? order : items;
  const shown = base.filter((i) => !q || `${i.label} ${i.hint ?? ""}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="checklist">
      {search && items.length > 8 && (
        <input type="search" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search the list" />
      )}
      <ul>
        {shown.map((i) => (
          <li key={i.value}>
            <label>
              <input type="checkbox" checked={selected.includes(i.value)} onChange={() => onToggle(i.value)} />
              <span><span className="cl-label">{i.label}</span>{i.hint && <span className="cl-hint">{i.hint}</span>}</span>
            </label>
          </li>
        ))}
        {shown.length === 0 && <li className="quiet">{empty}</li>}
      </ul>
    </div>
  );
}
