"use client";

import { useState, useEffect } from "react";

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
  created_at: string;
}

interface HotTopic {
  rank: number;
  title: string;
  author: string;
  genre: string;
  gender: string;  // spec v1.4.1：百度 genre 映射的性向
  hot_index: number;
  description: string;
}

interface GenreDist {
  genre: string;
  count: number;
  percentage: number;
}

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: "",
    synopsis: "",
    // 2026-09-14 平台化：平台决定 gender（频道）与 genre（品类）的合法取值域
    platform: "baidu" as string,
    gender: "无性向" as string,  // spec v1.4.0：新增性向；平台化后承载"频道"
    genre: "恐怖推理",
    target_word_count: 60000,
    initial_chapters: 10,
    total_chapters: 30,
    daily_chapters: 2,
  });
  const [editingId, setEditingId] = useState<string | null>(null);

  // 一键生成相关状态
  const [showHotWizard, setShowHotWizard] = useState(false);
  const [hotStep, setHotStep] = useState<"topics" | "synopsis" | "title">("topics");
  const [hotLoading, setHotLoading] = useState(false);
  const [hotTopics, setHotTopics] = useState<HotTopic[]>([]);
  const [genreDist, setGenreDist] = useState<GenreDist[]>([]);
  const [degraded, setDegraded] = useState(false);
  const [hotGenre, setHotGenre] = useState("恐怖推理");  // spec v1.4.0：默认无性向/恐怖推理
  const [synopses, setSynopses] = useState<string[]>([]);
  const [selectedSynopsis, setSelectedSynopsis] = useState("");
  const [titles, setTitles] = useState<string[]>([]);
  const [hotError, setHotError] = useState("");
  const [selectedTopicRanks, setSelectedTopicRanks] = useState<number[]>([]); // spec 5.4.1 规则 5b：默认勾选 Top 3
  const [hotGender, setHotGender] = useState<string>("");  // spec v1.4.1：热点向导性向筛选（空=全部）

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      const res = await fetch("/api/v1/projects");
      const data = await res.json();
      setProjects(data.items || []);
    } catch (e) {
      console.error(e);
    }
  };

  const createProject = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await fetch("/api/v1/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setShowCreate(false);
      setForm({ name: "", synopsis: "", platform: "baidu", gender: "无性向", genre: "恐怖推理", target_word_count: 60000, initial_chapters: 10, total_chapters: 30, daily_chapters: 2 });
      fetchProjects();
    } catch (e) {
      console.error(e);
    }
  };

  const triggerGenerate = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/projects/${id}/generate`, { method: "POST" });
      if (!res.ok) {
        const d = await res.json().catch(() => ({ detail: "请求失败" }));
        if (res.status === 409) {
          alert("项目正在生成中，请勿重复点击。如果长时间无进展，可能任务已丢失，请刷新页面后重试。");
        } else {
          alert(d.detail || `生成失败（${res.status}）`);
        }
        return;
      }
      fetchProjects();
    } catch (e) {
      console.error(e);
      alert("网络错误，请检查服务是否正常运行");
    }
  };

  const deleteProject = async (id: string, name: string) => {
    if (!confirm(`确定删除项目「${name}」吗？\n该操作会同时删除所有章节和封面，且不可恢复。`)) return;
    try {
      const res = await fetch(`/api/v1/projects/${id}`, { method: "DELETE" });
      if (!res.ok) {
        const d = await res.json().catch(() => ({ detail: "删除失败" }));
        alert(d.detail || `删除失败（${res.status}）`);
        return;
      }
      fetchProjects();
    } catch (e) {
      console.error(e);
      alert("网络错误，删除失败");
    }
  };

  const startEdit = (p: Project) => {
    setForm({
      name: p.name,
      synopsis: p.synopsis,
      platform: p.platform || "baidu",
      gender: p.gender,
      genre: p.genre,
      target_word_count: p.target_word_count,
      initial_chapters: p.initial_chapters,
      daily_chapters: p.daily_chapters,
    });
    setEditingId(p.id);
    setShowCreate(false);
  };

  const saveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingId) return;
    try {
      const res = await fetch(`/api/v1/projects/${editingId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({ detail: "修改失败" }));
        alert(d.detail || `修改失败（${res.status}）`);
        return;
      }
      setEditingId(null);
      setForm({ name: "", synopsis: "", platform: "baidu", gender: "无性向", genre: "恐怖推理", target_word_count: 60000, initial_chapters: 10, total_chapters: 30, daily_chapters: 2 });
      fetchProjects();
    } catch (e) {
      console.error(e);
      alert("网络错误，修改失败");
    }
  };

  // 一键生成：获取热点（spec v1.4.1：支持按性向筛选）
  const fetchHotTopics = async (gender: string = "") => {
    setHotLoading(true);
    setHotError("");
    try {
      const params = new URLSearchParams({ top_n: "20" });
      if (gender) params.set("gender", gender);
      const res = await fetch(`/api/v1/hot-topics/novel?${params}`);
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || "获取热点失败");
      }
      const data = await res.json();
      setHotTopics(data.topics || []);
      setGenreDist(data.genre_distribution || []);
      setDegraded(data.degraded || false);
      // spec 5.4.1 规则 5b：默认勾选 Top 3
      setSelectedTopicRanks((data.topics || []).slice(0, 3).map((t: HotTopic) => t.rank));
      setHotStep("topics");
      setShowHotWizard(true);
    } catch (e: any) {
      setHotError(e.message || "网络错误");
    } finally {
      setHotLoading(false);
    }
  };

  // spec v1.4.1：切换热点性向筛选，重新获取 top 20，题材下拉框联动跳到该性向的第一个
  const switchHotGender = (gender: string) => {
    setHotGender(gender);
    // 题材下拉框联动：切换性向后，若当前题材不在该性向列表中，则取第一个
    if (gender && !genresByGender[gender]?.includes(hotGenre)) {
      setHotGenre(genresByGender[gender]?.[0] || "");
    }
    fetchHotTopics(gender);
  };

  // spec v1.4.1：选择题材时联动 top 20（反推性向，重新获取该性向的热点）
  const handleHotGenreChange = (genre: string) => {
    setHotGenre(genre);
    // 根据题材反推性向，重新获取 top 20
    const inferredGender = Object.entries(genresByGender).find(([_, gs]) => gs.includes(genre))?.[0] || "";
    if (inferredGender !== hotGender) {
      setHotGender(inferredGender);
      fetchHotTopics(inferredGender);
    }
  };

  // 一键生成：生成梗概（spec 5.4.1 规则 5c：未勾选时提示）
  const generateSynopsis = async () => {
    if (selectedTopicRanks.length === 0) {
      setHotError("请至少选择 1 本参考小说");
      return;
    }
    setHotLoading(true);
    setHotError("");
    try {
      // spec 5.4.1 规则 5：用勾选的书名作为 reference_topics
      const refTopics = hotTopics
        .filter(t => selectedTopicRanks.includes(t.rank))
        .map(t => t.title);
      const res = await fetch("/api/v1/hot-topics/generate-synopsis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ genre: hotGenre, reference_topics: refTopics, count: 3 }),
      });
      if (!res.ok) {
        const d = await res.json();
        // spec v1.4.1：detail 可能是字符串或验证错误数组（422），统一提取可读消息
        const msg = Array.isArray(d.detail) ? d.detail.map((v: any) => v.msg || JSON.stringify(v)).join("; ") : (d.detail || "生成梗概失败");
        throw new Error(msg);
      }
      const data = await res.json();
      setSynopses(data.synopses || []);
      setSelectedSynopsis("");
      setHotStep("synopsis");
    } catch (e: any) {
      setHotError(typeof e === "string" ? e : (e?.message || "网络错误"));
    } finally {
      setHotLoading(false);
    }
  };

  // 一键生成：生成标题
  const generateTitles = async (synopsis: string) => {
    setHotLoading(true);
    setHotError("");
    try {
      const res = await fetch("/api/v1/hot-topics/generate-title", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ synopsis, genre: hotGenre, count: 5 }),
      });
      if (!res.ok) {
        const d = await res.json();
        const msg = Array.isArray(d.detail) ? d.detail.map((v: any) => v.msg || JSON.stringify(v)).join("; ") : (d.detail || "生成标题失败");
        throw new Error(msg);
      }
      const data = await res.json();
      setSelectedSynopsis(synopsis);
      setTitles(data.titles || []);
      setHotStep("title");
    } catch (e: any) {
      setHotError(typeof e === "string" ? e : (e?.message || "网络错误"));
    } finally {
      setHotLoading(false);
    }
  };

  // 切换勾选参考小说（spec 5.4.1 规则 5b：最多 3 本）
  const toggleTopic = (rank: number) => {
    setSelectedTopicRanks(prev => {
      if (prev.includes(rank)) {
        return prev.filter(r => r !== rank);
      }
      if (prev.length >= 3) {
        setHotError("最多只能选择 3 本参考小说，请先取消一个再选");
        return prev;
      }
      setHotError("");
      return [...prev, rank];
    });
  };

  // 选定标题后自动填表单
  const applyToForm = (title: string) => {
    // spec v1.4.0：根据 hotGenre 反推 gender
    const inferredGender = Object.entries(genresByGender).find(([_, gs]) => gs.includes(hotGenre))?.[0] || "无性向";
    setForm({
      ...form,
      name: title,
      synopsis: selectedSynopsis,
      gender: inferredGender,
      genre: hotGenre,
    });
    setShowHotWizard(false);
    setShowCreate(true);
  };

  const statusLabel: Record<string, string> = {
    draft: "草稿", generating: "生成中", pending_review: "待审核",
    reviewed: "已审核", publishing: "发布中", published: "已发布",
  };

  // 2026-09-14 平台化：与后端 app/config/platforms.py 保持一致。
  // 改动分类时两边都要动，或改为从 GET /api/v1/projects/platforms 拉取。
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
  const platformList = Object.keys(PLATFORM_META);
  const curPlatform = PLATFORM_META[form.platform] || PLATFORM_META.baidu;
  // spec v1.4.0：按 gender 分组的二级类型（现按平台动态取）
  const genresByGender: Record<string, string[]> = curPlatform.genresByGender;
  const genders = curPlatform.genders;

  // 切换平台：重置频道与品类到新平台的第一个合法值
  const switchPlatform = (platform: string) => {
    const meta = PLATFORM_META[platform] || PLATFORM_META.baidu;
    const g0 = meta.genders[0];
    const genre0 = (meta.genresByGender[g0] || [])[0] || "";
    setForm({ ...form, platform, gender: g0, genre: genre0 });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">小说项目</h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">管理你的AI小说创作项目</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => fetchHotTopics(hotGender)} disabled={hotLoading}>
            {hotLoading ? "加载中..." : "🔥 一键生成"}
          </button>
          <button className="btn-primary" onClick={() => setShowCreate(true)}>
            + 新建项目
          </button>
        </div>
      </div>

      {hotError && (
        <div className="mb-4 p-3 text-sm bg-[var(--danger)]/20 border border-[var(--danger)] rounded text-[var(--danger)]">
          {hotError}
        </div>
      )}

      {/* 一键生成向导 */}
      {showHotWizard && (
        <div className="card mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">
              一键生成项目
              {degraded && <span className="ml-2 text-xs text-[var(--warning)]">（降级模式：百度热搜不可达，使用本地知识库）</span>}
            </h2>
            <button className="text-[var(--text-secondary)] hover:text-[var(--danger)]" onClick={() => setShowHotWizard(false)}>✕</button>
          </div>

          {/* 步骤指示 */}
          <div className="flex gap-2 mb-4 text-xs">
            <span className={`px-2 py-1 rounded ${hotStep === "topics" ? "bg-[var(--accent)] text-white" : "bg-[var(--bg-secondary)]"}`}>1. 选择题材</span>
            <span className={`px-2 py-1 rounded ${hotStep === "synopsis" ? "bg-[var(--accent)] text-white" : "bg-[var(--bg-secondary)]"}`}>2. 选梗概</span>
            <span className={`px-2 py-1 rounded ${hotStep === "title" ? "bg-[var(--accent)] text-white" : "bg-[var(--bg-secondary)]"}`}>3. 选标题</span>
          </div>

          {/* 步骤 1：热点列表 + 选题材 */}
          {hotStep === "topics" && (
            <div className="space-y-4">
              {/* spec v1.4.1：性向筛选，切换性向重新获取 top 20 */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm text-[var(--text-secondary)]">性向筛选：</span>
                {["", "男性向", "女性向", "无性向"].map(g => (
                  <button
                    key={g || "all"}
                    className={`px-3 py-1 text-xs rounded border ${hotGender === g ? "bg-[var(--accent)] text-white border-[var(--accent)]" : "bg-[var(--bg-secondary)] border-transparent text-[var(--text-secondary)]"}`}
                    onClick={() => switchHotGender(g)}
                    disabled={hotLoading}
                  >
                    {g || "全部"}
                  </button>
                ))}
              </div>
              <div>
                <label className="block text-sm text-[var(--text-secondary)] mb-2">
                  当前百度热搜小说榜 Top {hotTopics.length}（勾选 1-3 本作为生成梗概的参考，已选 {selectedTopicRanks.length}/3）
                </label>
                <div className="max-h-[300px] overflow-y-auto space-y-2">
                  {hotTopics.map(t => {
                    const checked = selectedTopicRanks.includes(t.rank);
                    const disabled = !checked && selectedTopicRanks.length >= 3;
                    return (
                      <label
                        key={t.rank}
                        className={`flex items-start gap-2 p-2 rounded text-sm cursor-pointer border ${checked ? "bg-[var(--accent)]/15 border-[var(--accent)]" : "bg-[var(--bg-secondary)] border-transparent"} ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
                      >
                        <input
                          type="checkbox"
                          className="mt-1"
                          checked={checked}
                          disabled={disabled}
                          onChange={() => toggleTopic(t.rank)}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex justify-between">
                            <span className="font-medium">#{t.rank} {t.title}</span>
                            <span className="text-xs text-[var(--text-secondary)]">热度 {t.hot_index}</span>
                          </div>
                          <div className="text-xs text-[var(--text-secondary)] mt-1">{t.author} · {t.genre} · <span className="text-[var(--accent)]">{t.gender || "无性向"}</span></div>
                          <div className="text-xs mt-1 line-clamp-2">{t.description}</div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
              {genreDist.length > 0 && (
                <div>
                  <label className="block text-sm text-[var(--text-secondary)] mb-2">题材分布</label>
                  <div className="flex flex-wrap gap-2">
                    {genreDist.map(d => (
                      <span key={d.genre} className="text-xs px-2 py-1 bg-[var(--bg-secondary)] rounded">
                        {d.genre} {d.percentage}%
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <div>
                <label className="block text-sm text-[var(--text-secondary)] mb-1">选择你的题材</label>
                <select className="input" value={hotGenre} onChange={e => handleHotGenreChange(e.target.value)}>
                  {Object.entries(genresByGender).map(([gender, gs]) => (
                    <optgroup key={gender} label={gender}>
                      {gs.map(g => <option key={g} value={g}>{g}</option>)}
                    </optgroup>
                  ))}
                </select>
              </div>
              <div className="flex gap-2">
                <button
                  className="btn-primary"
                  onClick={generateSynopsis}
                  disabled={hotLoading || selectedTopicRanks.length === 0}
                  title={selectedTopicRanks.length === 0 ? "请至少选择 1 本参考小说" : ""}
                >
                  {hotLoading ? "生成中..." : "下一步：生成梗概 →"}
                </button>
                <button className="btn-secondary" onClick={() => setShowHotWizard(false)}>取消</button>
              </div>
            </div>
          )}

          {/* 步骤 2：选梗概 */}
          {hotStep === "synopsis" && (
            <div className="space-y-4">
              <label className="block text-sm text-[var(--text-secondary)]">候选梗概（题材：{hotGenre}）</label>
              {synopses.map((s, i) => (
                <div key={i} className="p-3 bg-[var(--bg-secondary)] rounded">
                  <p className="text-sm whitespace-pre-line">{s}</p>
                  <div className="flex gap-2 mt-2">
                    <button className="btn-primary text-xs py-1 px-3" onClick={() => generateTitles(s)} disabled={hotLoading}>
                      选这个并生成标题
                    </button>
                  </div>
                </div>
              ))}
              <div className="flex gap-2">
                <button className="btn-secondary" onClick={() => setHotStep("topics")} disabled={hotLoading}>← 上一步</button>
                <button className="btn-secondary" onClick={generateSynopsis} disabled={hotLoading}>重新生成</button>
              </div>
            </div>
          )}

          {/* 步骤 3：选标题 */}
          {hotStep === "title" && (
            <div className="space-y-4">
              <div className="p-3 bg-[var(--bg-secondary)] rounded">
                <label className="block text-xs text-[var(--text-secondary)] mb-1">已选梗概</label>
                <p className="text-sm whitespace-pre-line">{selectedSynopsis}</p>
              </div>
              <label className="block text-sm text-[var(--text-secondary)]">候选标题</label>
              <div className="space-y-2">
                {titles.map((t, i) => (
                  <div key={i} className="flex items-center justify-between p-2 bg-[var(--bg-secondary)] rounded">
                    <span className="text-sm font-medium">{t}</span>
                    <button className="btn-primary text-xs py-1 px-3" onClick={() => applyToForm(t)} disabled={hotLoading}>
                      选这个
                    </button>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <button className="btn-secondary" onClick={() => setHotStep("synopsis")} disabled={hotLoading}>← 上一步</button>
                <button className="btn-secondary" onClick={() => generateTitles(selectedSynopsis)} disabled={hotLoading}>重新生成标题</button>
              </div>
            </div>
          )}
        </div>
      )}

      {showCreate && !editingId && (
        <div className="card mb-8">
          <h2 className="text-lg font-semibold mb-4">创建新项目</h2>
          <form onSubmit={createProject} className="space-y-4">
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">目标平台</label>
              <select className="input" value={form.platform} onChange={e => switchPlatform(e.target.value)}>
                {platformList.map(k => <option key={k} value={k}>{PLATFORM_META[k].label}</option>)}
              </select>
              <p className="text-xs text-[var(--text-secondary)] mt-1">
                平台决定可选的频道/品类与书名、节奏规则。
                {form.platform !== "baidu" && "（该平台自动发布尚未接通，生成后需手动上传）"}
              </p>
            </div>
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">项目名称</label>
              <input className="input" value={form.name} onChange={e => setForm({...form, name: e.target.value})} required />
            </div>
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">故事梗概</label>
              <textarea className="input" rows={4} value={form.synopsis} onChange={e => setForm({...form, synopsis: e.target.value})} required minLength={10} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-[var(--text-secondary)] mb-1">{form.platform === "fanqie" ? "频道" : "作品性向"}</label>
                <select className="input" value={form.gender} onChange={e => {
                  const newGender = e.target.value;
                  const newGenres = genresByGender[newGender] || [];
                  const newGenre = newGenres.includes(form.genre) ? form.genre : newGenres[0];
                  setForm({...form, gender: newGender, genre: newGenre});
                }}>
                  {genders.map(g => <option key={g} value={g}>{g}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm text-[var(--text-secondary)] mb-1">题材分类</label>
                <select className="input" value={form.genre} onChange={e => setForm({...form, genre: e.target.value})}>
                  {(genresByGender[form.gender] || []).map(g => <option key={g} value={g}>{g}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm text-[var(--text-secondary)] mb-1">目标字数</label>
                <input className="input" type="number" value={form.target_word_count} onChange={e => setForm({...form, target_word_count: parseInt(e.target.value)})} min={10000} max={300000} />
              </div>
              <div>
                <label className="block text-sm text-[var(--text-secondary)] mb-1">首次生成章节数</label>
                <input className="input" type="number" value={form.initial_chapters} onChange={e => setForm({...form, initial_chapters: parseInt(e.target.value)})} min={1} max={50} />
              </div>
              <div>
                <label className="block text-sm text-[var(--text-secondary)] mb-1">日更章节数</label>
                <input className="input" type="number" value={form.daily_chapters} onChange={e => setForm({...form, daily_chapters: parseInt(e.target.value)})} min={1} max={5} />
              </div>
            </div>
            <div className="flex gap-3">
              <button type="submit" className="btn-primary">创建</button>
              <button type="button" className="btn-secondary" onClick={() => setShowCreate(false)}>取消</button>
            </div>
          </form>
        </div>
      )}

      {editingId && (
        <div className="card mb-8">
          <h2 className="text-lg font-semibold mb-4">编辑项目</h2>
          <form onSubmit={saveEdit} className="space-y-4">
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">目标平台</label>
              <select className="input" value={form.platform} onChange={e => switchPlatform(e.target.value)}>
                {platformList.map(k => <option key={k} value={k}>{PLATFORM_META[k].label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">项目名称</label>
              <input className="input" value={form.name} onChange={e => setForm({...form, name: e.target.value})} required />
            </div>
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">故事梗概</label>
              <textarea className="input" rows={4} value={form.synopsis} onChange={e => setForm({...form, synopsis: e.target.value})} required minLength={10} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-[var(--text-secondary)] mb-1">{form.platform === "fanqie" ? "频道" : "作品性向"}</label>
                <select className="input" value={form.gender} onChange={e => {
                  const newGender = e.target.value;
                  const newGenres = genresByGender[newGender] || [];
                  const newGenre = newGenres.includes(form.genre) ? form.genre : newGenres[0];
                  setForm({...form, gender: newGender, genre: newGenre});
                }}>
                  {genders.map(g => <option key={g} value={g}>{g}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm text-[var(--text-secondary)] mb-1">题材分类</label>
                <select className="input" value={form.genre} onChange={e => setForm({...form, genre: e.target.value})}>
                  {(genresByGender[form.gender] || []).map(g => <option key={g} value={g}>{g}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm text-[var(--text-secondary)] mb-1">目标字数</label>
                <input className="input" type="number" value={form.target_word_count} onChange={e => setForm({...form, target_word_count: parseInt(e.target.value)})} min={10000} max={300000} />
              </div>
              <div>
                <label className="block text-sm text-[var(--text-secondary)] mb-1">首次生成章节数</label>
                <input className="input" type="number" value={form.initial_chapters} onChange={e => setForm({...form, initial_chapters: parseInt(e.target.value)})} min={1} max={50} />
              </div>
              <div>
                <label className="block text-sm text-[var(--text-secondary)] mb-1">日更章节数</label>
                <input className="input" type="number" value={form.daily_chapters} onChange={e => setForm({...form, daily_chapters: parseInt(e.target.value)})} min={1} max={5} />
              </div>
            </div>
            <div className="flex gap-3">
              <button type="submit" className="btn-primary">保存修改</button>
              <button type="button" className="btn-secondary" onClick={() => { setEditingId(null); setForm({ name: "", synopsis: "", platform: "baidu", gender: "无性向", genre: "恐怖推理", target_word_count: 60000, initial_chapters: 10, total_chapters: 30, daily_chapters: 2 }); }}>取消</button>
            </div>
          </form>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {projects.map(p => (
          <div key={p.id} className="card hover:border-[var(--accent)] transition-colors cursor-pointer">
            <div className="flex items-start justify-between mb-3">
              <h3 className="font-semibold text-lg">{p.name}</h3>
              <span className={`badge badge-${p.status}`}>{statusLabel[p.status] || p.status}</span>
            </div>
            <p className="text-[var(--text-secondary)] text-sm mb-4 line-clamp-2">{p.synopsis}</p>
            <div className="flex items-center gap-4 text-xs text-[var(--text-secondary)] mb-4">
              <span className="px-1.5 py-0.5 rounded bg-[var(--bg-secondary)]">{PLATFORM_META[p.platform]?.label || "百度作家平台"}</span>
              <span>{p.gender}</span>
              <span>{p.genre}</span>
              <span>{p.target_word_count.toLocaleString()}字</span>
              <span>{p.initial_chapters}章</span>
            </div>
            <div className="flex gap-2 flex-wrap">
              <a href={`/project/${p.id}`} className="btn-secondary text-xs py-1 px-3">查看详情</a>
              {p.status === "draft" && (
                <button className="btn-primary text-xs py-1 px-3" onClick={() => triggerGenerate(p.id)}>
                  开始生成
                </button>
              )}
              <button className="btn-secondary text-xs py-1 px-3" onClick={() => startEdit(p)} title="编辑项目信息">
                编辑
              </button>
              <button
                className="text-xs py-1 px-3 rounded border border-[var(--danger)]/40 text-[var(--danger)] hover:bg-[var(--danger)]/10 transition-colors"
                onClick={() => deleteProject(p.id, p.name)}
                title="删除项目（不可恢复）"
              >
                删除
              </button>
            </div>
          </div>
        ))}
        {projects.length === 0 && (
          <div className="col-span-full text-center py-20 text-[var(--text-secondary)]">
            <p className="text-lg mb-2">暂无项目</p>
            <p className="text-sm">点击"新建项目"开始创作</p>
          </div>
        )}
      </div>
    </div>
  );
}