"use client";

import { useState, useEffect, useRef } from "react";

interface Project {
  id: string;
  name: string;
  status: string;
}

interface LoginStatus {
  status: "idle" | "pending" | "success" | "failed" | "error";
  message: string;
  cookie_count?: number;
  updated_at?: string;
}

export default function PublishPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [cookieValid, setCookieValid] = useState(false);
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginStatus, setLoginStatus] = useState<LoginStatus | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    fetchProjects();
    checkCookie();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const fetchProjects = async () => {
    try {
      const res = await fetch("/api/v1/projects");
      const data = await res.json();
      setProjects(data.items || []);
    } catch (e) { console.error(e); }
  };

  const checkCookie = async () => {
    try {
      const res = await fetch("/api/v1/publish/cookie-status");
      const data = await res.json();
      setCookieValid(data.cookie_valid);
    } catch (e) { console.error(e); }
  };

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const pollLoginStatus = () => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch("/api/v1/publish/login-status");
        const data: LoginStatus = await res.json();
        setLoginStatus(data);
        if (data.status === "success") {
          stopPolling();
          setLoginLoading(false);
          checkCookie();
        } else if (data.status === "failed" || data.status === "error") {
          stopPolling();
          setLoginLoading(false);
        }
      } catch (e) {
        console.error(e);
      }
    }, 2000);
  };

  const loginBaidu = async () => {
    setLoginLoading(true);
    setLoginStatus({ status: "pending", message: "正在派发登录任务..." });
    try {
      const res = await fetch("/api/v1/publish/login", { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        setLoginStatus({ status: "pending", message: data.message });
        // 开始轮询登录状态
        pollLoginStatus();
      } else {
        setLoginStatus({ status: "failed", message: `派发失败：${data.detail || "未知错误"}` });
        setLoginLoading(false);
      }
    } catch (e) {
      console.error(e);
      setLoginStatus({ status: "failed", message: "网络错误，请查看后端日志" });
      setLoginLoading(false);
    }
  };

  const cancelLogin = async () => {
    stopPolling();
    setLoginLoading(false);
    try {
      await fetch("/api/v1/publish/login-cancel", { method: "POST" });
      setLoginStatus(null);
    } catch (e) { console.error(e); }
  };

  const publishProject = async (id: string) => {
    if (!confirm("确认发布？请确保所有章节已审核通过。")) return;
    try {
      const res = await fetch(`/api/v1/publish/project/${id}`, { method: "POST" });
      const data = await res.json();
      alert(data.message);
    } catch (e) { console.error(e); }
  };

  const statusLabel: Record<string, string> = {
    draft: "草稿", generating: "生成中", pending_review: "待审核",
    reviewed: "已审核", publishing: "发布中", published: "已发布",
  };

  const loginStatusColor: Record<string, string> = {
    pending: "border-[var(--accent)] text-[var(--accent)]",
    success: "border-[var(--success)] text-[var(--success)]",
    failed: "border-[var(--danger)] text-[var(--danger)]",
    error: "border-[var(--danger)] text-[var(--danger)]",
    idle: "border-[var(--text-secondary)]",
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">发布管理</h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">管理百度作家平台发布</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${cookieValid ? "bg-[var(--success)]" : "bg-[var(--danger)]"}`}></div>
            <span className="text-sm text-[var(--text-secondary)]">{cookieValid ? "Cookie有效" : "Cookie无效"}</span>
          </div>
          <button className="btn-secondary" onClick={checkCookie}>检查Cookie</button>
          {!loginLoading ? (
            <button className="btn-primary" onClick={loginBaidu}>登录百度</button>
          ) : (
            <button className="btn-secondary" onClick={cancelLogin}>取消登录</button>
          )}
        </div>
      </div>

      {loginStatus && (
        <div className={`card mb-6 whitespace-pre-line text-sm border-l-4 ${loginStatusColor[loginStatus.status] || ""}`}>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold">
              {loginStatus.status === "pending" && "登录中..."}
              {loginStatus.status === "success" && "登录成功"}
              {loginStatus.status === "failed" && "登录失败"}
              {loginStatus.status === "error" && "状态错误"}
            </span>
            {loginStatus.status === "pending" && (
              <span className="text-xs animate-pulse">（每2秒自动刷新状态）</span>
            )}
          </div>
          <div className="text-[var(--text-secondary)]">{loginStatus.message}</div>
          {loginStatus.cookie_count ? (
            <div className="text-xs mt-1">Cookie 数量：{loginStatus.cookie_count}</div>
          ) : null}
          {loginStatus.status === "success" && (
            <div className="text-xs mt-2 text-[var(--success)]">现在可以发布章节了</div>
          )}
          {loginStatus.status === "failed" && (
            <div className="text-xs mt-2">请检查浏览器是否被拦截，或重试登录</div>
          )}
        </div>
      )}

      <div className="card mb-8">
        <h2 className="font-semibold mb-4">发布须知</h2>
        <ul className="space-y-2 text-sm text-[var(--text-secondary)]">
          <li>1. 首次发布需手动登录百度账号获取Cookie（点击右上角"登录百度"）</li>
          <li>2. 浏览器会以独立进程打开，登录完成后状态会自动更新为"登录成功"</li>
          <li>3. 只有审核通过的章节才能发布</li>
          <li>4. 发布后需等待平台审核（约1周）</li>
          <li>5. Cookie过期前24小时系统会提醒重新登录</li>
          <li>6. 发布间隔不低于5分钟，每日不超过10章</li>
        </ul>
      </div>

      <div className="space-y-3">
        {projects.map(p => (
          <div key={p.id} className="card flex items-center justify-between">
            <div>
              <h3 className="font-semibold">{p.name}</h3>
              <span className={`badge badge-${p.status} mt-1`}>{statusLabel[p.status] || p.status}</span>
            </div>
            <div className="flex gap-3">
              {p.status === "reviewed" && (
                <button className="btn-primary" onClick={() => publishProject(p.id)}>发布到百度</button>
              )}
              <a href={`/project/${p.id}`} className="btn-secondary text-sm">查看详情</a>
            </div>
          </div>
        ))}
        {projects.length === 0 && (
          <div className="text-center py-16 text-[var(--text-secondary)]">暂无项目</div>
        )}
      </div>
    </div>
  );
}
