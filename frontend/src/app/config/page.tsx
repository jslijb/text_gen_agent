"use client";

import { useState, useEffect } from "react";

interface ModelInfo {
  name: string;
  base_url: string;
  api_key_env: string;
  quota: number;
  priority: number;
  role: string | null;
  tokens_used: number;
  call_count: number;
  status: string;
}

interface ConfigItem {
  key: string;
  value: any;
  description: string | null;
  effective: boolean;
  updated_at: string;
}

export default function ConfigPage() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [configs, setConfigs] = useState<ConfigItem[]>([]);

  useEffect(() => {
    fetchModels();
    fetchConfigs();
  }, []);

  const fetchModels = async () => {
    try {
      const res = await fetch("/api/v1/config/models");
      setModels(await res.json());
    } catch (e) { console.error(e); }
  };

  const fetchConfigs = async () => {
    try {
      const res = await fetch("/api/v1/config");
      setConfigs(await res.json());
    } catch (e) { console.error(e); }
  };

  const reloadModels = async () => {
    try {
      const res = await fetch("/api/v1/config/models/reload", { method: "POST" });
      const data = await res.json();
      alert(data.message);
      fetchModels();
    } catch (e) { console.error(e); }
  };

  const statusColor: Record<string, string> = {
    available: "var(--success)", exhausted: "var(--danger)", unreachable: "var(--warning)",
  };

  const roleLabel: Record<string, string> = {
    planner: "规划", writer: "写作", reviewer: "审稿", reviser: "修订", humanizer: "去AI化",
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">系统配置</h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">管理模型配置和运行时参数</p>
        </div>
        <button className="btn-primary" onClick={reloadModels}>重载模型配置</button>
      </div>

      <div className="card mb-8">
        <h2 className="font-semibold mb-4">模型状态</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[var(--text-secondary)] border-b border-[var(--border)]">
                <th className="text-left py-3 px-2">优先级</th>
                <th className="text-left py-3 px-2">模型</th>
                <th className="text-left py-3 px-2">角色</th>
                <th className="text-left py-3 px-2">状态</th>
                <th className="text-left py-3 px-2">额度</th>
                <th className="text-left py-3 px-2">已用</th>
                <th className="text-left py-3 px-2">调用次数</th>
                <th className="text-left py-3 px-2">用量</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m, i) => {
                const usagePercent = m.quota > 0 ? (m.tokens_used / m.quota * 100) : 0;
                return (
                  <tr key={i} className="border-b border-[var(--border)]/50">
                    <td className="py-3 px-2">{m.priority}</td>
                    <td className="py-3 px-2 font-mono">{m.name}</td>
                    <td className="py-3 px-2">{m.role ? roleLabel[m.role] || m.role : "通用"}</td>
                    <td className="py-3 px-2">
                      <span style={{ color: statusColor[m.status] || "inherit" }}>{m.status}</span>
                    </td>
                    <td className="py-3 px-2">{(m.quota / 10000).toFixed(0)}万</td>
                    <td className="py-3 px-2">{(m.tokens_used / 10000).toFixed(1)}万</td>
                    <td className="py-3 px-2">{m.call_count}</td>
                    <td className="py-3 px-2">
                      <div className="progress-bar w-24">
                        <div className="progress-bar-fill" style={{ width: `${Math.min(usagePercent, 100)}%` }}></div>
                      </div>
                      <span className="text-xs text-[var(--text-secondary)] ml-2">{usagePercent.toFixed(1)}%</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {models.length === 0 && (
          <p className="text-center py-8 text-[var(--text-secondary)]">未加载到模型配置</p>
        )}
      </div>

      <div className="card">
        <h2 className="font-semibold mb-4">运行时配置</h2>
        <div className="space-y-3">
          {configs.map(c => (
            <div key={c.key} className="flex items-center justify-between p-3 bg-[var(--bg-secondary)] rounded-lg">
              <div>
                <div className="font-medium text-sm">{c.key}</div>
                {c.description && <div className="text-xs text-[var(--text-secondary)]">{c.description}</div>}
              </div>
              <div className="flex items-center gap-3">
                <code className="text-xs bg-[var(--bg-primary)] px-2 py-1 rounded">{JSON.stringify(c.value)}</code>
                <span className={`w-2 h-2 rounded-full ${c.effective ? "bg-[var(--success)]" : "bg-[var(--warning)]"}`}></span>
              </div>
            </div>
          ))}
          {configs.length === 0 && (
            <p className="text-center py-8 text-[var(--text-secondary)]">暂无运行时配置</p>
          )}
        </div>
      </div>
    </div>
  );
}