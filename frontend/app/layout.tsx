import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { NotificationBell } from "@/components/NotificationBell";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Car Bargains",
  description: "Detección de chollos y riesgos en anuncios de coches de segunda mano",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="es"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <header className="border-b border-neutral-200 dark:border-neutral-800">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
            <Link href="/" className="text-lg font-bold tracking-tight">
              Car<span className="text-blue-600">Bargains</span>
            </Link>
<nav className="flex items-center gap-4 text-sm text-neutral-600 dark:text-neutral-400">
              <Link href="/" className="hover:text-neutral-900 dark:hover:text-neutral-100">
                Activos
              </Link>
              <Link href="/importar" className="hover:text-neutral-900 dark:hover:text-neutral-100">
                Importar
              </Link>
              <Link href="/historico" className="hover:text-neutral-900 dark:hover:text-neutral-100">
                Histórico
              </Link>
              <Link href="/health" className="hover:text-neutral-900 dark:hover:text-neutral-100">
                Salud
              </Link>
              <NotificationBell />
            </nav>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-neutral-200 py-4 text-center text-xs text-neutral-500 dark:border-neutral-800">
          Car Bargains · backend en localhost:8000
        </footer>
      </body>
    </html>
  );
}
