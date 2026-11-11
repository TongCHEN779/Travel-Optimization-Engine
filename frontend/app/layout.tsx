import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Travel Optimization Engine",
  description: "Multi-objective Pareto itinerary search",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
