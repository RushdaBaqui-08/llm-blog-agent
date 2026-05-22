import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Blog Writing Agent - AI Publisher",
  description: "Generate comprehensive technical blog posts with research, evidence synthesis, task-planning, parallel writing, and image assets.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="app-container">
          {children}
        </div>
      </body>
    </html>
  );
}
