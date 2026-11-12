"use client";
import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

export interface Tab { id: string; label: string; count?: number; content: ReactNode }

/** Underline tabs. Arrow keys move between tabs; the bar scrolls sideways on small screens. */
export function Tabs({ tabs, initial }: { tabs: Tab[]; initial?: string }) {
  const shown = tabs.filter(Boolean);
  const [active, setActive] = useState(initial && shown.some((t) => t.id === initial) ? initial : shown[0]?.id);
  const base = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  function key(e: KeyboardEvent, i: number) {
    const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!d) return;
    const j = (i + d + shown.length) % shown.length;
    setActive(shown[j].id);
    refs.current[j]?.focus();
  }
  return (
    <div className="tabset">
      <div className="tabbar" role="tablist">
        {shown.map((t, i) => (
          <button key={t.id} ref={(el) => { refs.current[i] = el; }} role="tab" type="button"
                  id={`${base}-${t.id}`} aria-controls={`${base}-${t.id}-panel`}
                  aria-selected={active === t.id} tabIndex={active === t.id ? 0 : -1}
                  onClick={() => setActive(t.id)} onKeyDown={(e) => key(e, i)}>
            {t.label}{typeof t.count === "number" ? <span className="tab-count">{t.count}</span> : null}
          </button>
        ))}
      </div>
      {shown.map((t) => (
        <div key={t.id} role="tabpanel" id={`${base}-${t.id}-panel`} aria-labelledby={`${base}-${t.id}`}
             hidden={active !== t.id} className="tabpanel">
          {t.content}
        </div>
      ))}
    </div>
  );
}
