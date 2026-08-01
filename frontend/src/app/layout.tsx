import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "imaginAI — تحويل الأفكار إلى فيديو",
  description: "أداة ذكاء اصطناعي لتحويل أفكارك ونصوصك المكتوبة إلى فيديوهات جاهزة تلقائياً بضغطة واحدة.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ar" className="h-full antialiased dark select-none">
      <body className="min-h-full flex flex-col bg-[#0a0a0a] text-[#f5f5f5]">{children}</body>
    </html>
  );
}
