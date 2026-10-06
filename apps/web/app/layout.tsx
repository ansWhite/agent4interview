import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "InsightAgent · Research Control Room",
  description: "可控、可观测、可评测的 Deep Research Agent",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
