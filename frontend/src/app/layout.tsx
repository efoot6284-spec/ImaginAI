import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Cairo, Almarai, Montserrat, Poppins } from "next/font/google";
import "./globals.css";

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-plus-jakarta",
  display: "swap",
});

const cairo = Cairo({
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-cairo",
  display: "swap",
});

const almarai = Almarai({
  subsets: ["arabic"],
  weight: ["400", "700", "800"],
  variable: "--font-almarai",
  display: "swap",
});

const montserrat = Montserrat({
  subsets: ["latin"],
  weight: ["400", "600", "700", "800"],
  variable: "--font-montserrat",
  display: "swap",
});

const poppins = Poppins({
  subsets: ["latin"],
  weight: ["400", "600", "700", "800"],
  variable: "--font-poppins",
  display: "swap",
});

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
    <html lang="ar" className={`h-full antialiased dark select-none ${plusJakartaSans.variable} ${cairo.variable} ${almarai.variable} ${montserrat.variable} ${poppins.variable}`}>
      <body className="min-h-full flex flex-col bg-[#0a0a0a] text-[#f5f5f5] font-sans">
        {children}
      </body>
    </html>
  );
}
