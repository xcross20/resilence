import type { ReactNode } from "react";
import { DestinationNav } from "@/components/destination-nav";
import "./globals.css";

export const metadata = {
  title: "Execution Optimizer",
  description: "Synthetic demonstration workbench for persisted execution evidence.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="demo-strip">
          <span>Synthetic Demo</span>
          <span>Not production authority</span>
        </div>
        <div className="shell">
          <DestinationNav />
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
