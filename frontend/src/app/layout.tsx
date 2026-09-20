import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI小说生成系统",
  description: "AI生成 → 去AI化 → 人工终审 → 发布",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen">
        <nav className="border-b border-[var(--border)] bg-[var(--bg-secondary)] px-6 py-3">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <a href="/" className="text-lg font-bold text-[var(--accent)]">
              AI Novel Studio
            </a>
            <div className="flex gap-6 text-sm text-[var(--text-secondary)]">
              <a href="/" className="hover:text-[var(--text-primary)] transition-colors">项目</a>
              <a href="/knowledge" className="hover:text-[var(--text-primary)] transition-colors">知识库</a>
              <a href="/publish" className="hover:text-[var(--text-primary)] transition-colors">发布</a>
              <a href="/config" className="hover:text-[var(--text-primary)] transition-colors">配置</a>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-6 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}