import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "TinyURL Lab",
  description: "A simple URL shortener system design project",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
