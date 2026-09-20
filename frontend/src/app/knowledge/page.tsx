"use client";

import { useState, useEffect } from "react";

interface KnowledgeEntry {
  id: string;
  topic: string;
  word_count_range: string;
  opening_pattern: string;
  emotion_type: string;
  ending_type: string;
  source: string;
  heat_score: number | null;
  ttl_days: number;
  vectorized: boolean;
  content: string;
}

export default function KnowledgePage() {
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [stats, setStats] = useState({ total_entries: 0, vectorized_entries: 0, topics: {} as Record<string, number>, avg_heat_score: 0 });

  useEffect(() => {
    fetchEntries();
    fetchStats();
  }, []);

  const fetchEntries = async () => {
    try {
      const res = await fetch("/api/v1/knowledge");
      const data = await res.json();
      setEntries(data.items || []);
    } catch (e) { console.error(e); }
  };

  const fetchStats = async () => {
    try {
      const res = await fetch("/api/v1/knowledge/stats");
      setStats(await res.json());
    } catch (e) { console.error(e); }
  };

  const searchKnowledge = async () => {
    if (!searchQuery.trim()) { fetchEntries(); return; }
    try {
      const params = new URLSearchParams({ query: searchQuery, n_results: "10" });
      const res = await fetch(`/api/v1/knowledge/search?${params.toString()}`);
      setEntries(await res.json());
    } catch (e) { console.error(e); }
  };

  const triggerScrape = async () => {
    try {
      await fetch("/api/v1/knowledge/scrape", { method: "POST" });
      alert("爆款抓取任务已提交");
    } catch (e) { console.error(e); }
  };

  const triggerCleanup = async () => {
    try {
      await fetch("/api/v1/knowledge/cleanup", { method: "POST" });
      alert("过期清理任务已提交");
    } catch (e) { console.error(e); }
  };

  const deleteEntry = async (id: string) => {
    if (!confirm("确认删除此条目？")) return;
    try {
      await fetch(`/api/v1/knowledge/${id}`, { method: "DELETE" });
      fetchEntries();
      fetchStats();
    } catch (e) { console.error(e); }
  };

  const emotionLabel: Record<string, string> = {
    thrill: "爽感", heartbreak: "虐心", tension: "紧张", warmth: "温馨", reversal: "反转",
  };
  const endingLabel: Record<string, string> = {
    happy: "大团圆", open: "开放式", reversal: "反转", tragic: "悲剧",
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">爆款知识库</h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">管理百度作家平台爆款小说特征</p>
        </div>
        <div className="flex gap-3">
          <button className="btn-secondary" onClick={triggerScrape}>抓取爆款</button>
          <button className="btn-secondary" onClick={triggerCleanup}>清理过期</button>
          <button className="btn-primary" onClick={() => setShowAdd(true)}>+ 添加条目</button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="card text-center">
          <div className="text-2xl font-bold text-[var(--accent)]">{stats.total_entries}</div>
          <div className="text-xs text-[var(--text-secondary)] mt-1">总条目数</div>
        </div>
        <div className="card text-center">
          <div className="text-2xl font-bold text-[var(--success)]">{stats.vectorized_entries}</div>
          <div className="text-xs text-[var(--text-secondary)] mt-1">已向量化</div>
        </div>
        <div className="card text-center">
          <div className="text-2xl font-bold text-[var(--warning)]">{stats.avg_heat_score.toFixed(1)}</div>
          <div className="text-xs text-[var(--text-secondary)] mt-1">平均热度</div>
        </div>
        <div className="card text-center">
          <div className="text-2xl font-bold">{Object.keys(stats.topics).length}</div>
          <div className="text-xs text-[var(--text-secondary)] mt-1">题材分类</div>
        </div>
      </div>

      <div className="flex gap-3 mb-6">
        <input className="input flex-1" placeholder="搜索知识库..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} onKeyDown={e => e.key === "Enter" && searchKnowledge()} />
        <button className="btn-primary" onClick={searchKnowledge}>搜索</button>
      </div>

      <div className="space-y-3">
        {entries.map(e => (
          <div key={e.id} className="card flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <span className="badge bg-[var(--accent)]/20 text-[var(--accent)]">{e.topic}</span>
                <span className="text-xs text-[var(--text-secondary)]">{emotionLabel[e.emotion_type] || e.emotion_type}</span>
                <span className="text-xs text-[var(--text-secondary)]">{endingLabel[e.ending_type] || e.ending_type}</span>
                {e.heat_score != null && <span className="text-xs text-[var(--warning)]">热度:{e.heat_score.toFixed(0)}</span>}
                {e.vectorized && <span className="text-xs text-[var(--success)]">已向量化</span>}
              </div>
              <p className="text-sm text-[var(--text-secondary)] line-clamp-2">{e.content}</p>
              <p className="text-xs text-[var(--text-secondary)] mt-2">来源: {e.source} | TTL: {e.ttl_days}天</p>
            </div>
            <button className="text-[var(--danger)] text-xs ml-4 hover:underline" onClick={() => deleteEntry(e.id)}>删除</button>
          </div>
        ))}
        {entries.length === 0 && (
          <div className="text-center py-16 text-[var(--text-secondary)]">知识库为空，点击"抓取爆款"或手动添加</div>
        )}
      </div>
    </div>
  );
}