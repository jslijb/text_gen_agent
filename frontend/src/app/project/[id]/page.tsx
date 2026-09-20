"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams } from "next/navigation";

// 2026-09-14 平台化：分类体系与后端 app/config/platforms.py 保持一致
const PLATFORM_META: Record<string, { label: string; genders: string[]; genresByGender: Record<string, string[]> }> = {
  baidu: {
    label: "百度作家平台",
    genders: ["男性向", "女性向", "无性向"],
    genresByGender: {
      "男性向": ["都市情感", "历史故事"],
      "女性向": ["现代言情", "古代言情", "青春校园", "婚姻家庭"],
      "无性向": ["恐怖推理", "乡村故事", "真实故事", "见闻杂谈", "复仇爽文", "特殊职业"],
    },
  },
  fanqie: {
    label: "番茄小说",
    genders: ["女频", "男频"],
    genresByGender: {
      "女频": ["女频脑洞", "现言甜宠", "青春虐恋", "古言甜宠", "古言虐恋", "宫斗宅斗", "民国旧影", "年代", "女性成长", "都市日常", "悬疑惊悚"],
      "男频": ["男频脑洞", "玄幻仙侠", "历史古代", "都市日常", "悬疑惊悚"],
    },
  },
};

interface Chapter {
  id: string;
  chapter_number: number;
  title: string;
  content: string;
  ai_score_before: number | null;
  ai_score_after: number | null;
  review_status: string;
  publish_status: string;
  model_used: string | null;
}

interface Project {
  id: string;
  name: string;
  synopsis: string;
  platform: string;  // 2026-09-14 平台化：baidu / fanqie
  gender: string;  // spec v1.4.0：新增性向；平台化后承载"频道"
  genre: string;
  target_word_count: number;
  initial_chapters: number;
  total_chapters: number;
  daily_chapters: number;
  status: string;
  cover_url?: string | null;
  titles?: string[] | null;
}

export default function ProjectDetail() {
  const params = useParams();
  const id = params.id as string;
  const [project, setProject] = useState<Project | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<Chapter | null>(null);
  const [editContent, setEditContent] = useState("");
  const [editTitle, setEditTitle] = useState("");
  const [humanizeStrategy, setHumanizeStrategy] = useState("adversarial");
  const [humanizeMsg, setHumanizeMsg] = useState("");
  const [copyMsg, setCopyMsg] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  // 任务状态: idle(无任务) | running(执行中) | paused(已暂停) | stopped(已停止)
  const [taskStatus, setTaskStatus] = useState<"idle" | "running" | "paused" | "stopped">("idle");
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);
  const taskPollRef = useRef<number | null>(null);
  // 检测"假排队"：连续 N 次轮询 task_state=PENDING 但进度无变化 → 判定任务丢失
  const staleCountRef = useRef(0);
  const lastProgressRef = useRef<string>("");

  // 封面生成相关状态（spec 5.8）
  const [coverUrl, setCoverUrl] = useState<string | null>(null);
  const [showCoverPanel, setShowCoverPanel] = useState(false);
  const [coverGender, setCoverGender] = useState<string>("无性向");
  const [coverGenre, setCoverGenre] = useState("悬疑");
  const [coverLoading, setCoverLoading] = useState(false);
  const [coverError, setCoverError] = useState("");
  const [uploadingCover, setUploadingCover] = useState(false);

  // 2026-09-15 连载：续写状态。
  // 此前前端没有任何续写入口，连载只能依赖后端定时任务，
  // 而定时任务在 Docker 部署下根本没跑起来 —— 界面完全推不动连载。
  const [continuing, setContinuing] = useState(false);
  const [continueMsg, setContinueMsg] = useState("");
  const [continueBatch, setContinueBatch] = useState(2);

  // 2026-09-14 平台化：分类体系随项目所属平台切换（百度 / 番茄）
  const curPlatformMeta = PLATFORM_META[project?.platform || "baidu"] || PLATFORM_META.baidu;
  const genresByGenderMap: Record<string, string[]> = curPlatformMeta.genresByGender;

  const fetchProject = useCallback(async () => {
    try {
      const res = await fetch(`/api/v1/projects/${id}`);
      const data = await res.json();
      setProject(data);
      // 同步封面 URL、性向、题材（spec 5.8.1 规则 6 v1.4.0）
      setCoverUrl(data.cover_url || null);
      if (data.gender) setCoverGender(data.gender);
      if (data.genre) setCoverGenre(data.genre);
    } catch (e) { console.error(e); }
  }, [id]);

  const fetchChapters = useCallback(async () => {
    try {
      const res = await fetch(`/api/v1/projects/${id}/chapters`);
      const data = await res.json();
      const items: Chapter[] = data.items || [];
      setChapters(items);
      setLastRefresh(new Date());
      // 同步当前选中章节的内容（去AI化后内容会更新）
      setSelectedChapter(prev => {
        if (!prev) return prev;
        const updated = items.find(c => c.id === prev.id);
        if (updated && updated.content !== editContent) {
          // 仅在用户未手动编辑时同步（避免覆盖用户编辑）
          setEditContent(updated.content);
        }
        return updated || prev;
      });
    } catch (e) { console.error(e); }
  }, [id, editContent]);

  useEffect(() => {
    fetchProject();
    fetchChapters();
    // 从 localStorage 恢复任务状态（避免刷新页面后前端丢失 task_id）
    const savedTaskId = localStorage.getItem(`humanize_task_${id}`);
    const savedStatus = localStorage.getItem(`humanize_status_${id}`) as "running" | "paused" | "stopped" | null;
    if (savedTaskId && savedStatus === "running") {
      setCurrentTaskId(savedTaskId);
      setTaskStatus("running");
      pollTaskStatus(savedTaskId);
    } else if (savedStatus === "paused") {
      setTaskStatus("paused");
    }
    return () => {
      if (taskPollRef.current) clearTimeout(taskPollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // 自动刷新：5 秒轮询章节列表 + 项目状态（生成中检测完成、去AI化进度可见）
  useEffect(() => {
    if (!autoRefresh) {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    pollRef.current = setInterval(() => {
      fetchChapters();
      fetchProject();
    }, 5000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [autoRefresh, fetchChapters, fetchProject]);

  const selectChapter = (ch: Chapter) => {
    setSelectedChapter(ch);
    setEditContent(ch.content);
    setEditTitle(ch.title);
  };

  const saveChapter = async () => {
    if (!selectedChapter) return;
    try {
      await fetch(`/api/v1/projects/${id}/chapters/${selectedChapter.chapter_number}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: editContent, title: editTitle }),
      });
      fetchChapters();
    } catch (e) { console.error(e); }
  };

  const triggerHumanize = async () => {
    if (!selectedChapter) return;
    setHumanizeMsg(`正在对第 ${selectedChapter.chapter_number} 章执行去AI化，请耐心等待（对抗性改写约1-2分钟）...`);
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 300000);
      const res = await fetch(`/api/v1/projects/${id}/chapters/${selectedChapter.chapter_number}/humanize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy: humanizeStrategy }),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      const data = await res.json();
      if (res.ok) {
        setHumanizeMsg(`第 ${selectedChapter.chapter_number} 章去AI化完成！分数：${data.ai_score_before ?? "?"} → ${data.ai_score_after ?? "?"}`);
        fetchChapters();
      } else {
        setHumanizeMsg(`提交失败：${data.detail || JSON.stringify(data)}`);
      }
    } catch (e: any) {
      console.error(e);
      if (e.name === "AbortError") {
        setHumanizeMsg("请求超时（5分钟），请查看后端日志确认是否完成");
      } else {
        setHumanizeMsg("网络错误，请查看后端日志");
      }
    }
  };

  const triggerHumanizeAll = async () => {
    // 检测已有进度：换策略重跑必须先清空（后端断点续跑会跳过已有 ai_score_after 的章节）
    if (humanizeProgress.completed > 0) {
      const confirmed = confirm(
        `检测到已有 ${humanizeProgress.completed}/${humanizeProgress.total} 章去AI化记录。\n` +
        `后端断点续跑机制会跳过已处理章节，导致新策略无法真正执行。\n\n` +
        `使用新策略重跑需要先清空所有进度（ai_score_before/after 清空，内容恢复原文），是否继续？`
      );
      if (!confirmed) return;
      setHumanizeMsg("正在清空旧进度...");
      try {
        const stopRes = await fetch(`/api/v1/projects/${id}/chapters/humanize-stop?task_id=${currentTaskId || ""}`, { method: "POST" });
        if (!stopRes.ok) {
          setHumanizeMsg("清空进度失败，请重试");
          return;
        }
        await fetchChapters(); // 刷新章节列表（进度已清空）
        setHumanizeMsg("旧进度已清空，开始提交新任务...");
      } catch (e) {
        console.error(e);
        setHumanizeMsg("清空进度网络错误");
        return;
      }
    }
    if (!confirm(`确认对全部 ${chapters.length} 章执行去AI化？\n策略：${humanizeStrategy === "adversarial" ? "对抗性改写(检测器反馈循环,推荐)" : humanizeStrategy === "quick" ? "快速" : humanizeStrategy === "recursive" ? "递归释义(3轮×3候选)" : "标准"}\n注意：对抗性改写/递归释义模式每章约 3-9 分钟，8 章约 30-70 分钟`)) return;
    setHumanizeMsg(`正在提交全局去AI化任务（共 ${chapters.length} 章）...`);
    try {
      const res = await fetch(`/api/v1/projects/${id}/chapters/humanize-all`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy: humanizeStrategy }),
      });
      const data = await res.json();
      if (res.ok) {
        setHumanizeMsg(`已提交：${data.message}`);
        setAutoRefresh(true);
        // 保存 task_id + 状态到 localStorage（刷新页面后可恢复）
        if (data.task_id) {
          setCurrentTaskId(data.task_id);
          setTaskStatus("running");
          localStorage.setItem(`humanize_task_${id}`, data.task_id);
          localStorage.setItem(`humanize_status_${id}`, "running");
          staleCountRef.current = 0;
          lastProgressRef.current = "";
          pollTaskStatus(data.task_id);
        }
      } else {
        setHumanizeMsg(`提交失败：${data.detail || "未知错误"}`);
      }
    } catch (e) {
      console.error(e);
      setHumanizeMsg("网络错误，请查看后端日志");
    }
  };

  // 暂停：保留进度，下次启动从断点继续
  const handlePause = async () => {
    if (!currentTaskId) return;
    try {
      const res = await fetch(`/api/v1/projects/${id}/chapters/humanize-pause?task_id=${currentTaskId}`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        setTaskStatus("paused");
        localStorage.setItem(`humanize_status_${id}`, "paused");
        setHumanizeMsg(`⏸ 已暂停：${data.message}`);
        // 停止轮询（任务会被 revoke）
        if (taskPollRef.current) {
          clearTimeout(taskPollRef.current);
          taskPollRef.current = null;
        }
      } else {
        setHumanizeMsg(`暂停失败：${data.detail || "未知错误"}`);
      }
    } catch (e) {
      console.error(e);
      setHumanizeMsg("暂停请求网络错误");
    }
  };

  // 停止：清除所有进度，下次启动从头开始
  const handleStop = async () => {
    if (!confirm("确认停止去AI化？\n停止后会清除所有章节的去AI化进度（ai_score_before/after 清空，内容恢复原文），下次启动从头开始。\n已暂停的进度也会被清空。")) return;
    try {
      const res = await fetch(`/api/v1/projects/${id}/chapters/humanize-stop?task_id=${currentTaskId || ""}`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        setTaskStatus("stopped");
        setCurrentTaskId(null);
        localStorage.removeItem(`humanize_task_${id}`);
        localStorage.removeItem(`humanize_status_${id}`);
        setHumanizeMsg(`⏹ 已停止：${data.message}`);
        // 停止轮询
        if (taskPollRef.current) {
          clearTimeout(taskPollRef.current);
          taskPollRef.current = null;
        }
        fetchChapters(); // 立即刷新（进度被清空）
      } else {
        setHumanizeMsg(`停止失败：${data.detail || "未知错误"}`);
      }
    } catch (e) {
      console.error(e);
      setHumanizeMsg("停止请求网络错误");
    }
  };

  // 继续：从断点恢复（后端 humanize_project 会跳过已有 ai_score_after 的章节）
  const handleResume = async () => {
    if (!confirm(`从断点继续去AI化？\n策略：${humanizeStrategy === "quick" ? "快速" : humanizeStrategy === "recursive" ? "递归释义(Agnes AI)" : "标准"}\n已处理的章节会自动跳过。`)) return;
    setHumanizeMsg("正在提交继续任务...");
    try {
      const res = await fetch(`/api/v1/projects/${id}/chapters/humanize-all`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy: humanizeStrategy }),
      });
      const data = await res.json();
      if (res.ok) {
        setHumanizeMsg(`已恢复：${data.message}`);
        setAutoRefresh(true);
        if (data.task_id) {
          setCurrentTaskId(data.task_id);
          setTaskStatus("running");
          localStorage.setItem(`humanize_task_${id}`, data.task_id);
          localStorage.setItem(`humanize_status_${id}`, "running");
          staleCountRef.current = 0;
          lastProgressRef.current = "";
          pollTaskStatus(data.task_id);
        }
      } else {
        setHumanizeMsg(`恢复失败：${data.detail || "未知错误"}`);
      }
    } catch (e) {
      console.error(e);
      setHumanizeMsg("恢复请求网络错误");
    }
  };

  // 任务状态轮询：每 3 秒查 humanize-status，显示 task_state + 真实进度
  // 修复"假排队"：Celery 对未知 task_id 返回 PENDING，需用进度变化判断任务是否真的在跑
  const pollTaskStatus = (taskId: string) => {
    const stateLabel: Record<string, string> = {
      PENDING: "排队中",
      STARTED: "执行中",
      SUCCESS: "已完成",
      FAILURE: "失败",
      RETRY: "重试中",
      UNKNOWN: "未知",
    };
    const poll = async () => {
      try {
        const res = await fetch(`/api/v1/projects/${id}/chapters/humanize-status?task_id=${taskId}`);
        const data = await res.json();
        const pct = data.progress_pct ?? 0;
        const state = data.task_state || "PENDING";
        const progressKey = `${data.completed}/${data.total_chapters}`;
        // 快速判定：进度 100% 但 task_state=PENDING（task_id 已过期）→ 实际已完成
        if (state === "PENDING" && data.total_chapters > 0 && data.completed >= data.total_chapters) {
          setTaskStatus("idle");
          setCurrentTaskId(null);
          localStorage.removeItem(`humanize_task_${id}`);
          localStorage.removeItem(`humanize_status_${id}`);
          setHumanizeMsg(`✓ 去AI化已完成：${data.completed}/${data.total_chapters} 章已处理（任务记录已自动清理）`);
          return;
        }
        // 检测"假排队"：state=PENDING 且进度无变化 → 累计 stale 计数
        if (state === "PENDING" && progressKey === lastProgressRef.current) {
          staleCountRef.current += 1;
        } else {
          staleCountRef.current = 0;
        }
        lastProgressRef.current = progressKey;
        // 连续 6 次（约 18 秒）PENDING 且进度无变化 → 任务已丢失（worker 没启动 / 任务被清理）
        if (staleCountRef.current >= 6) {
          setTaskStatus("idle");
          setCurrentTaskId(null);
          localStorage.removeItem(`humanize_task_${id}`);
          localStorage.removeItem(`humanize_status_${id}`);
          setHumanizeMsg(`⚠ 任务状态异常：Celery 中查不到任务 ${taskId}（可能 worker 未启动或任务已完成被清理）。当前实际进度：${data.completed}/${data.total_chapters} (${pct}%)。如需重跑请点击"全局去AI化"。`);
          return;
        }
        setHumanizeMsg(`任务状态：${stateLabel[state] || state} | 进度：${data.completed}/${data.total_chapters} (${pct}%)`);
        fetchChapters();
        if (state === "SUCCESS") {
          setTaskStatus("idle");
          setCurrentTaskId(null);
          localStorage.removeItem(`humanize_task_${id}`);
          localStorage.removeItem(`humanize_status_${id}`);
          setHumanizeMsg(`✓ 去AI化完成：${data.completed}/${data.total_chapters} 章已处理`);
          return;
        }
        if (state === "FAILURE") {
          setTaskStatus("idle");
          setCurrentTaskId(null);
          localStorage.removeItem(`humanize_task_${id}`);
          localStorage.removeItem(`humanize_status_${id}`);
          setHumanizeMsg(`✗ 任务失败：${data.task_result || "请查看后端日志"}`);
          return;
        }
        taskPollRef.current = window.setTimeout(poll, 3000);
      } catch (e) {
        console.error(e);
        taskPollRef.current = window.setTimeout(poll, 5000);
      }
    };
    poll();
  };

  const approveChapter = async (chNum: number) => {
    try {
      await fetch(`/api/v1/projects/${id}/chapters/${chNum}/approve`, { method: "POST" });
      fetchChapters();
    } catch (e) { console.error(e); }
  };

  const rejectChapter = async (chNum: number) => {
    const comment = prompt("请输入拒绝原因（可选）：") || "";
    try {
      await fetch(`/api/v1/projects/${id}/chapters/${chNum}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment }),
      });
      fetchChapters();
    } catch (e) { console.error(e); }
  };

  // 一键复制全文：拼接所有章节标题+内容
  const copyAllText = async () => {
    if (chapters.length === 0) {
      setCopyMsg("暂无章节可复制");
      setTimeout(() => setCopyMsg(""), 2000);
      return;
    }
    const fullText = chapters
      .map(ch => `第${ch.chapter_number}章 ${ch.title}\n\n${ch.content}`)
      .join("\n\n" + "=".repeat(40) + "\n\n");
    try {
      await navigator.clipboard.writeText(fullText);
      const totalChars = fullText.length;
      setCopyMsg(`已复制全部 ${chapters.length} 章到剪贴板（约 ${totalChars} 字）`);
    } catch (e) {
      // 降级方案：用 textarea
      const textarea = document.createElement("textarea");
      textarea.value = fullText;
      document.body.appendChild(textarea);
      textarea.select();
      try {
        document.execCommand("copy");
        setCopyMsg(`已复制全部 ${chapters.length} 章到剪贴板（降级模式）`);
      } catch (err) {
        setCopyMsg("复制失败，请手动选择文本");
      }
      document.body.removeChild(textarea);
    }
    setTimeout(() => setCopyMsg(""), 4000);
  };

  // 批量去AI化进度统计
  const humanizeProgress = (() => {
    if (chapters.length === 0) return { completed: 0, total: 0, pct: 0, hasBefore: 0, avgDrop: 0 };
    const completed = chapters.filter(c => c.ai_score_after != null).length;
    const hasBefore = chapters.filter(c => c.ai_score_before != null).length;
    const drops = chapters.filter(c => c.ai_score_before != null && c.ai_score_after != null);
    const avgDrop = drops.length > 0
      ? drops.reduce((s, c) => s + ((c.ai_score_before! - c.ai_score_after!) / c.ai_score_before!), 0) / drops.length * 100
      : 0;
    return {
      completed,
      total: chapters.length,
      pct: Math.round((completed / chapters.length) * 100),
      hasBefore,
      avgDrop: Math.round(avgDrop),
    };
  })();

  const reviewStatusLabel: Record<string, string> = {
    pending: "待审核", approved: "已通过", rejected: "已拒绝",
  };
  const statusLabel: Record<string, string> = {
    draft: "草稿", generating: "生成中", pending_review: "待审核",
    reviewed: "已审核", publishing: "发布中", published: "已发布",
  };
  const reviewStatusColor: Record<string, string> = {
    pending: "text-[var(--warning)]",
    approved: "text-[var(--success)]",
    rejected: "text-[var(--danger)]",
  };
  const publishStatusLabel: Record<string, string> = {
    unpublished: "未发布", publishing: "发布中", published: "已发布",
    under_review: "审核中", approved: "已通过", rejected: "已拒绝",
  };

  // 生成封面（spec 5.8.1 规则 4）
  const generateCover = async () => {
    setCoverLoading(true);
    setCoverError("");
    try {
      const res = await fetch(`/api/v1/projects/${id}/cover/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gender: coverGender, genre: coverGenre }),
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || "封面生成失败");
      }
      const data = await res.json();
      setCoverUrl(data.cover_url);
      setShowCoverPanel(false);
    } catch (e: any) {
      setCoverError(e.message || "网络错误");
    } finally {
      setCoverLoading(false);
    }
  };

  const uploadCover = async (file: File) => {
    setUploadingCover(true);
    setCoverError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`/api/v1/projects/${id}/cover/upload`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({ detail: "上传失败" }));
        throw new Error(d.detail || `上传失败（${res.status}）`);
      }
      const data = await res.json();
      setCoverUrl(data.cover_url);
    } catch (e: any) {
      setCoverError(e.message || "网络错误");
    } finally {
      setUploadingCover(false);
    }
  };

  const continueWriting = async () => {
    setContinuing(true);
    setContinueMsg("");
    try {
      const res = await fetch(`/api/v1/projects/${id}/generate/daily?chapters=${continueBatch}`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `提交失败（${res.status}）`);
      setContinueMsg(
        `已提交续写：本次 ${data.batch_size} 章（已有 ${data.existing_chapters}/${data.total_chapters} 章）。` +
        `后台写作中，章节列表会自动刷新。`
      );
      fetchProject();
      fetchChapters();
    } catch (e: any) {
      setContinueMsg(`续写提交失败：${e.message || "网络错误"}`);
    } finally {
      setContinuing(false);
    }
  };

  if (!project) return <div className="text-[var(--text-secondary)]">加载中...</div>;

  const totalChaptersTarget = project.total_chapters || 30;
  const chapterProgressPct = Math.min(100, Math.round((chapters.length / totalChaptersTarget) * 100));
  const writtenWords = chapters.reduce((s, c) => s + (c.content?.length || 0), 0);
  const allWritten = chapters.length >= totalChaptersTarget;

  return (
    <div>
      <div className="mb-6">
        <a href="/" className="text-[var(--accent)] text-sm hover:underline">&larr; 返回项目列表</a>
        <h1 className="text-2xl font-bold mt-2">{project.name}</h1>
        <p className="text-[var(--text-secondary)] text-sm mt-1">{project.synopsis}</p>
        <div className="flex gap-4 mt-3 text-xs text-[var(--text-secondary)]">
          <span>{project.genre}</span>
          <span>{project.target_word_count.toLocaleString()}字</span>
          <span className={`badge badge-${project.status}`}>{statusLabel[project.status] || project.status}</span>
        </div>
        {project.status === "generating" && (
          <div className="mt-4 p-4 rounded-lg bg-[var(--bg-secondary)] border border-[var(--accent)]/30">
            <div className="flex items-center gap-3">
              <div className="w-4 h-4 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin"></div>
              <span className="text-sm text-[var(--accent)] font-medium">正在生成小说...</span>
              <span className="text-xs text-[var(--text-secondary)]">共 {project.initial_chapters} 章，AI 写作中（每5秒自动刷新）</span>
            </div>
            <div className="mt-3 h-2 bg-[var(--bg-primary)] rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-[var(--accent)] to-purple-400 rounded-full animate-pulse" style={{ width: "100%", opacity: 0.6 }}></div>
            </div>
          </div>
        )}
      </div>

      {/* 百度分发标题区域 */}
      <div className="card mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">分发标题</h2>
          <button
            className="btn-primary text-xs py-1"
            onClick={async () => {
              try {
                const res = await fetch(`/api/v1/projects/${id}/generate-titles`, { method: "POST" });
                const data = await res.json();
                if (res.ok && data.titles) {
                  setProject(prev => prev ? { ...prev, titles: data.titles } : prev);
                }
              } catch (e) { console.error(e); }
            }}
          >
            {project?.titles?.length ? "重新生成" : "生成标题"}
          </button>
        </div>
        {project?.titles?.length ? (
          <div className="space-y-2">
            {project.titles.map((t, i) => (
              <div key={i} className="flex items-center gap-2 p-2 bg-[var(--bg-secondary)] rounded text-sm">
                <span className="text-[var(--text-secondary)] font-mono w-6">{i + 1}.</span>
                <span className="flex-1">{t}</span>
                <button
                  className="text-xs text-[var(--accent)] hover:underline"
                  onClick={() => navigator.clipboard.writeText(t)}
                >
                  复制
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-[var(--text-secondary)]">点击"生成标题"为百度平台生成分发标题（17-30字）</div>
        )}
      </div>

      {/* 封面区域（spec 5.8） */}
      <div className="card mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">小说封面</h2>
          <div className="flex gap-2">
            {coverUrl && (
              <a
                href={coverUrl}
                download={`${project.name}_封面.png`}
                className="btn-secondary text-xs py-1"
              >
                下载封面
              </a>
            )}
            <label className="btn-secondary text-xs py-1 cursor-pointer" title="上传自定义封面图片">
              {uploadingCover ? "上传中..." : "上传图片"}
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif"
                className="hidden"
                disabled={uploadingCover}
                onChange={e => {
                  const f = e.target.files?.[0];
                  if (f) uploadCover(f);
                  e.target.value = "";
                }}
              />
            </label>
            <button
              className="btn-primary text-xs py-1"
              onClick={() => setShowCoverPanel(!showCoverPanel)}
              disabled={coverLoading}
            >
              {coverLoading ? "生成中..." : (coverUrl ? "AI重新生成" : "AI生成封面")}
            </button>
          </div>
        </div>
        {coverError && (
          <div className="mb-3 p-2 text-sm bg-[var(--danger)]/20 border border-[var(--danger)] rounded text-[var(--danger)]">
            {coverError}
          </div>
        )}
        {showCoverPanel && (
          <div className="mb-4 p-4 bg-[var(--bg-secondary)] rounded space-y-3">
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-2">{project?.platform === "fanqie" ? "频道" : "作品性向"}</label>
              <div className="flex gap-2">
                {curPlatformMeta.genders.map(g => (
                  <button
                    key={g}
                    className={`text-xs px-3 py-1 rounded ${coverGender === g ? "bg-[var(--accent)] text-white" : "bg-[var(--bg)] border border-[var(--border)]"}`}
                    onClick={() => {
                      setCoverGender(g);
                      // spec v1.4.0：切换性向时联动更新类型
                      const newGenres = genresByGenderMap[g] || [];
                      if (!newGenres.includes(coverGenre)) setCoverGenre(newGenres[0]);
                    }}
                  >
                    {g}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">作品类型</label>
              <select className="input" value={coverGenre} onChange={e => setCoverGenre(e.target.value)}>
                {(genresByGenderMap[coverGender] || []).map(g => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            </div>
            <button
              className="btn-primary text-sm"
              onClick={generateCover}
              disabled={coverLoading}
            >
              {coverLoading ? "生成中（约 60-90 秒）..." : "开始生成"}
            </button>
          </div>
        )}
        {coverUrl ? (
          <div className="flex justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={coverUrl}
              alt={`${project.name} 封面`}
              className="max-h-96 rounded shadow-lg"
              onClick={() => window.open(coverUrl, "_blank")}
              style={{ cursor: "pointer" }}
            />
          </div>
        ) : (
          <div className="flex items-center justify-center h-48 bg-[var(--bg-secondary)] rounded text-[var(--text-secondary)] text-sm">
            暂无封面
          </div>
        )}
      </div>

      {/* 去 AI 化进度条 */}
      {chapters.length > 0 && (
        <div className="card mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold">去AI化进度</h2>
            <div className="flex items-center gap-3 text-xs">
              <label className="flex items-center gap-1 cursor-pointer">
                <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} />
                <span>自动刷新(5s)</span>
              </label>
              {lastRefresh && <span className="text-[var(--text-secondary)]">最后刷新: {lastRefresh.toLocaleTimeString()}</span>}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-3 bg-[var(--bg-secondary)] rounded-full overflow-hidden">
              <div
                className="h-full bg-[var(--accent)] transition-all duration-500"
                style={{ width: `${humanizeProgress.pct}%` }}
              ></div>
            </div>
            <span className="text-sm font-mono">去AI化: {humanizeProgress.completed}/{humanizeProgress.total} ({humanizeProgress.pct}%)</span>
          </div>
          <div className="flex gap-4 mt-2 text-xs text-[var(--text-secondary)]">
            <span>已评分(前): {humanizeProgress.hasBefore}/{humanizeProgress.total}</span>
            {humanizeProgress.completed > 0 && (
              <span>平均AI分数下降: {humanizeProgress.avgDrop}%</span>
            )}
          </div>
          {humanizeMsg && (
            <div className="mt-3 p-2 text-sm bg-[var(--bg-secondary)] rounded border-l-4 border-[var(--accent)] whitespace-pre-line">
              {humanizeMsg}
            </div>
          )}
        </div>
      )}

      {/* 连载进度与续写入口（2026-09-15 新增） */}
      <div className="card mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">连载进度</h2>
          <div className="flex items-center gap-2">
            <select
              className="input w-28 text-xs py-1"
              value={continueBatch}
              onChange={e => setContinueBatch(parseInt(e.target.value))}
              disabled={continuing}
            >
              {[1, 2, 3, 5].map(n => (
                <option key={n} value={n}>续写 {n} 章</option>
              ))}
            </select>
            <button
              className="btn-primary text-xs py-1"
              onClick={continueWriting}
              disabled={continuing || project.status === "generating" || allWritten}
              title={allWritten ? "已达目标章节数" : "按大纲续写下一批章节"}
            >
              {continuing ? "提交中..." : (allWritten ? "已完结" : "续写下一批")}
            </button>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex-1 h-3 bg-[var(--bg-secondary)] rounded-full overflow-hidden">
            <div
              className="h-full bg-[var(--accent)] transition-all duration-500"
              style={{ width: `${chapterProgressPct}%` }}
            ></div>
          </div>
          <span className="text-sm font-mono">{chapters.length}/{totalChaptersTarget} 章</span>
        </div>
        <div className="flex gap-4 mt-2 text-xs text-[var(--text-secondary)]">
          <span>首批 {project.initial_chapters} 章 · 日更 {project.daily_chapters} 章</span>
          <span>已写 {writtenWords.toLocaleString()} 字</span>
          <span>{project.platform === "fanqie" ? "番茄" : "百度"} · {chapters.length >= totalChaptersTarget ? "已完结" : `还差 ${totalChaptersTarget - chapters.length} 章`}</span>
        </div>
        {continueMsg && (
          <div className="mt-3 p-2 text-sm bg-[var(--bg-secondary)] rounded border-l-4 border-[var(--accent)]">
            {continueMsg}
          </div>
        )}
      </div>

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-4">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold">章节列表 ({chapters.length})</h2>
              <div className="flex gap-2">
                <button className="btn-secondary text-xs py-1" onClick={copyAllText} title="拼接所有章节内容到剪贴板">
                  一键复制全文
                </button>
              </div>
            </div>
            {copyMsg && (
              <div className="mb-3 p-2 text-xs bg-[var(--success)]/20 border border-[var(--success)] rounded text-[var(--success)]">
                {copyMsg}
              </div>
            )}
            {chapters.length > 0 && (
              <div className="mb-3 pb-3 border-b border-[var(--border)]">
                <div className="flex gap-2 items-center mb-2">
                  <select className="input w-28 text-xs py-1" value={humanizeStrategy} onChange={e => setHumanizeStrategy(e.target.value)} disabled={taskStatus === "running"}>
                    <option value="adversarial">对抗性改写(推荐)</option>
                    <option value="recursive">递归释义</option>
                    <option value="default">标准</option>
                    <option value="quick">快速</option>
                  </select>
                  {taskStatus === "running" ? (
                    <button className="btn-secondary text-xs py-1 flex-1 opacity-50 cursor-not-allowed" disabled title="任务进行中，请先暂停或停止">全局去AI化</button>
                  ) : (
                    <button className="btn-primary text-xs py-1 flex-1" onClick={triggerHumanizeAll}>全局去AI化</button>
                  )}
                </div>
                {/* 任务控制按钮：running 显示 暂停+停止；paused 显示 继续+停止；idle+已有进度 显示 清空进度 */}
                {(taskStatus === "running" || taskStatus === "paused") && (
                  <div className="flex gap-2">
                    {taskStatus === "running" ? (
                      <button
                        className="text-xs py-1 flex-1 px-3 rounded bg-[var(--warning)] text-white hover:opacity-90 font-medium"
                        onClick={handlePause}
                        title="暂停：保留当前进度，下次从断点继续"
                      >⏸ 暂停</button>
                    ) : (
                      <button
                        className="text-xs py-1 flex-1 px-3 rounded bg-[var(--success)] text-white hover:opacity-90 font-medium"
                        onClick={handleResume}
                        title="继续：从上次暂停的断点继续处理（已处理的章节会跳过）"
                      >▶ 继续</button>
                    )}
                    <button
                      className="text-xs py-1 flex-1 px-3 rounded bg-[var(--danger)] text-white hover:opacity-90 font-medium"
                      onClick={handleStop}
                      title="停止：清除所有去AI化进度，下次从头开始"
                    >⏹ 停止</button>
                  </div>
                )}
                {taskStatus === "idle" && humanizeProgress.completed > 0 && (
                  <div className="flex gap-2 mt-2">
                    <button
                      className="text-xs py-1 px-3 rounded bg-[var(--danger)]/80 text-white hover:opacity-90 font-medium"
                      onClick={handleStop}
                      title="清空所有去AI化进度（ai_score_before/after 清空，内容恢复原文），用于换策略重跑"
                    >🗑 清空进度（换策略重跑）</button>
                  </div>
                )}
                {taskStatus === "paused" && (
                  <p className="text-xs text-[var(--warning)] mt-1">已暂停，进度已保留。点击"继续"从断点恢复，或"停止"清空进度。</p>
                )}
              </div>
            )}
            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {chapters.map(ch => {
                const isSelected = selectedChapter?.id === ch.id;
                return (
                  <div
                    key={ch.id}
                    className={`p-3 rounded-lg cursor-pointer transition-colors ${isSelected ? "bg-[var(--accent)]/20 border border-[var(--accent)]" : "bg-[var(--bg-secondary)] hover:bg-[var(--bg-secondary)]/80"}`}
                    onClick={() => selectChapter(ch)}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">第{ch.chapter_number}章 {ch.title}</span>
                    </div>
                    <div className="flex flex-wrap gap-2 mt-1 text-xs items-center">
                      <span className={reviewStatusColor[ch.review_status] || ""}>
                        {reviewStatusLabel[ch.review_status] || ch.review_status}
                      </span>
                      <span className="text-[var(--text-secondary)]">·</span>
                      <span className="text-[var(--text-secondary)]">{publishStatusLabel[ch.publish_status] || ch.publish_status}</span>
                      {ch.ai_score_before != null && ch.ai_score_after != null && (
                        <span className="font-mono">
                          AI: <span className="text-[var(--text-secondary)]">{ch.ai_score_before.toFixed(0)}</span>
                          {" → "}
                          <span className="text-[var(--success)]">{ch.ai_score_after.toFixed(0)}</span>
                        </span>
                      )}
                      {ch.ai_score_before != null && ch.ai_score_after == null && (
                        <span className="font-mono text-[var(--warning)]">
                          AI: {ch.ai_score_before.toFixed(0)} (待去AI化{taskStatus === "running" ? "·排队中" : ""})
                        </span>
                      )}
                    </div>
                    {/* 审核按钮：明显可见 */}
                    {ch.review_status === "pending" && (
                      <div className="flex gap-1 mt-2" onClick={e => e.stopPropagation()}>
                        <button
                          className="text-xs px-2 py-0.5 rounded bg-[var(--success)] text-white hover:opacity-80"
                          onClick={() => approveChapter(ch.chapter_number)}
                        >通过</button>
                        <button
                          className="text-xs px-2 py-0.5 rounded bg-[var(--danger)] text-white hover:opacity-80"
                          onClick={() => rejectChapter(ch.chapter_number)}
                        >拒绝</button>
                      </div>
                    )}
                  </div>
                );
              })}
              {chapters.length === 0 && (
                project.status === "generating" ? (
                  <div className="text-center py-12">
                    <div className="w-8 h-8 border-3 border-[var(--accent)] border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
                    <p className="text-[var(--accent)] text-sm font-medium">AI 正在写作中...</p>
                    <p className="text-[var(--text-secondary)] text-xs mt-2">生成完成后章节将自动显示</p>
                  </div>
                ) : (
                  <p className="text-[var(--text-secondary)] text-sm text-center py-8">暂无章节</p>
                )
              )}
            </div>
          </div>
        </div>

        <div className="col-span-8">
          {selectedChapter ? (
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <span className="text-sm text-[var(--text-secondary)] whitespace-nowrap">第{selectedChapter.chapter_number}章</span>
                  <input
                    className="input flex-1 text-sm py-1"
                    value={editTitle}
                    onChange={e => setEditTitle(e.target.value)}
                    placeholder="章节标题"
                  />
                </div>
                <div className="flex gap-2 ml-2">
                  <select className="input w-36 text-sm py-1" value={humanizeStrategy} onChange={e => setHumanizeStrategy(e.target.value)}>
                    <option value="adversarial">对抗性改写(推荐)</option>
                    <option value="recursive">递归释义</option>
                    <option value="default">标准去AI化</option>
                    <option value="quick">快速去AI化</option>
                  </select>
                  <button className="btn-primary text-xs py-1" onClick={triggerHumanize}>去AI化</button>
                  <button className="btn-primary text-xs py-1" onClick={saveChapter}>保存</button>
                </div>
              </div>

              {(selectedChapter.ai_score_before != null || selectedChapter.ai_score_after != null) && (
                <div className="flex gap-4 mb-4 text-sm">
                  {selectedChapter.ai_score_before != null && (
                    <span>去AI化前分数: <b>{selectedChapter.ai_score_before.toFixed(1)}</b></span>
                  )}
                  {selectedChapter.ai_score_after != null && (
                    <span>去AI化后分数: <b className="text-[var(--success)]">{selectedChapter.ai_score_after.toFixed(1)}</b></span>
                  )}
                </div>
              )}

              <textarea
                className="input w-full min-h-[500px] font-mono text-sm leading-relaxed"
                value={editContent}
                onChange={e => setEditContent(e.target.value)}
              />
            </div>
          ) : (
            <div className="card text-center py-20 text-[var(--text-secondary)]">
              <p>选择左侧章节查看和编辑</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
