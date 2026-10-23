"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const destinations = [
  ["/operate", "Operate"],
  ["/investigate", "Investigate"],
  ["/strategies", "Strategies"],
  ["/releases", "Releases"],
] as const;

export function DestinationNav() {
  const pathname = usePathname();
  return (
    <nav className="nav">
      <strong>Execution Optimizer</strong>
      <span>Service desk · persisted records</span>
      {destinations.map(([href, label]) => (
        <Link key={href} href={href} aria-current={pathname === href ? "page" : undefined}>{label}</Link>
      ))}
    </nav>
  );
}
