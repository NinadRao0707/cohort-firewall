import Link from "next/link";

export function Nav({ current }: { current: "question" | "release" }) {
  return (
    <nav className="tabs" aria-label="Checks">
      <Link href="/tower" aria-current={current === "release" ? "page" : undefined}>Release check</Link>
      <Link href="/" aria-current={current === "question" ? "page" : undefined}>Question check</Link>
    </nav>
  );
}
