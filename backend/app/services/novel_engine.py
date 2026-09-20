import json
import re
import logging
from typing import Optional
from app.agents import PlannerAgent, WriterAgent, ReviewerAgent, ReviserAgent
from app.config import platforms as pf
from app.services.knowledge_base import KnowledgeBaseManager

logger = logging.getLogger(__name__)

REVIEW_PASS_THRESHOLD = 70
MAX_REVISION_ROUNDS = 3

# 续写上下文规格（首批生成与日更续写共用，保证两代链条同构）
CONTEXT_SUMMARY_MAX_CHAPTERS = 8   # "前文脉络"最多回溯多少章
CONTEXT_TAIL_CHARS = 900           # "上一章正文尾部"截取字数


def count_words(text: str) -> int:
    """平台口径的正文字数：去掉空白（换行/空格），标点计入。

    用于校验章节是否落在 app/config/platforms.py 配置的 chapter_words 区间内。
    """
    if not text:
        return 0
    return len(re.sub(r"\s", "", text))


def _pick(obj, name, default=None):
    """从 dict 或对象上取值（同一函数既要能吃 ORM 对象，也要能吃轻量 dict）"""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def build_continuation_context(
    chapters_plan: list | None,
    written_chapters: list,
    max_summary: int = CONTEXT_SUMMARY_MAX_CHAPTERS,
    tail_chars: int = CONTEXT_TAIL_CHARS,
) -> tuple[str, str]:
    """构建续写上下文，返回 (前文脉络, 上一章正文尾部)。

    2026-09-15 修复连载脱节：原日更续写只把"最近 3 章的标题"当上下文，
    信息量远小于首批生成时使用的章节摘要，导致续写必然与前文脱节、重复叙述。
    现改为两代链条统一规格：

    - 前文脉络：优先取大纲里的 **章节摘要**（写清"谁做了什么、推进到什么状态"），
      取不到摘要才退回标题；
    - 上一章正文尾部：截取上一章正文最后若干字，让 writer 能接住
      场景、人物在场状态和未完成的动作。

    written_chapters 只需鸭子类型（含 chapter_number / title / content 属性），
    便于直接传 ORM 对象，也便于测试传轻量对象。
    """
    plan_by_num: dict[int, dict] = {}
    for item in chapters_plan or []:
        if not isinstance(item, dict):
            continue
        try:
            plan_by_num[int(item.get("number"))] = item
        except (TypeError, ValueError):
            continue

    lines: list[str] = []
    for ch in written_chapters or []:
        num = _pick(ch, "chapter_number")
        plan = plan_by_num.get(num) or {}
        title = (plan.get("title") or _pick(ch, "title", "") or "").strip()
        summary = (plan.get("summary") or "").strip()
        if summary:
            lines.append(f"第{num}章《{title}》：{summary}")
        else:
            lines.append(f"第{num}章《{title}》")
    previous_summary = "\n".join(lines[-max_summary:]) if lines else ""

    previous_tail = ""
    if written_chapters:
        content = (_pick(written_chapters[-1], "content", "") or "").strip()
        if content:
            previous_tail = content[-tail_chars:]

    return previous_summary, previous_tail


def _robust_json_parse(text: str) -> dict:
    """容错JSON解析：提取{}块→清理非法字符→解析，失败则逐步更激进清理"""
    # 先去掉markdown代码块包裹
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    
    for attempt in range(4):
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # 提取最外层{}块
            start = text.find("{")
            end = text.rfind("}") + 1
            if start < 0 or end <= start:
                break
            snippet = text[start:end]
            
            if attempt == 0:
                # 第1次：清理控制字符+尾逗号
                cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", snippet)
                cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
            elif attempt == 1:
                # 第2次：修复未转义的换行和引号（中文引号→英文引号）
                cleaned = snippet.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                cleaned = cleaned.replace('\u201c', '"').replace('\u201d', '"')
                cleaned = cleaned.replace('\u2018', '"').replace('\u2019', '"')
                cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
            elif attempt == 2:
                # 第3次：逐字符扫描，修复字符串内的非法字符
                cleaned = _fix_json_string_chars(snippet)
            else:
                # 第4次：尝试用正则提取关键字段
                result = _extract_outline_fields(snippet)
                if result:
                    return result
                break
            
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                text = snippet
                continue
    
    # 最后尝试正则提取
    result = _extract_outline_fields(text)
    if result:
        return result
    return {"raw": text, "parse_error": True}


def _fix_json_string_chars(text: str) -> str:
    """修复JSON字符串中常见的非法字符：逐字符处理，保留JSON结构"""
    result = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            result.append(ch)
            escape_next = False
            continue
        if ch == '\\':
            result.append(ch)
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            result.append(ch)
            continue
        if in_string:
            # 字符串内：换行→\\n，控制字符→删除
            if ch == '\n':
                result.append('\\n')
            elif ch == '\r':
                result.append('\\r')
            elif ch == '\t':
                result.append('\\t')
            elif ord(ch) < 0x20:
                pass  # 删除其他控制字符
            else:
                result.append(ch)
        else:
            result.append(ch)
    return ''.join(result)


def _extract_outline_fields(text: str) -> dict:
    """从LLM输出中用正则提取大纲关键字段（chapters/characters/foreshadowing）"""
    result = {}
    # 提取chapters数组
    ch_match = re.search(r'"chapters"\s*:\s*\[', text)
    if ch_match:
        # 找到chapters数组的起始位置，尝试解析
        arr_start = text.index('[', ch_match.start())
        arr_end = _find_matching_bracket(text, arr_start)
        if arr_end > arr_start:
            try:
                arr_text = text[arr_start:arr_end+1]
                # 清理后解析
                arr_text = _fix_json_string_chars(arr_text)
                result["chapters"] = json.loads(arr_text)
            except Exception:
                pass
    # 提取characters数组
    char_match = re.search(r'"characters"\s*:\s*\[', text)
    if char_match:
        arr_start = text.index('[', char_match.start())
        arr_end = _find_matching_bracket(text, arr_start)
        if arr_end > arr_start:
            try:
                arr_text = text[arr_start:arr_end+1]
                arr_text = _fix_json_string_chars(arr_text)
                result["characters"] = json.loads(arr_text)
            except Exception:
                pass
    # 提取foreshadowing数组
    fs_match = re.search(r'"foreshadowing"\s*:\s*\[', text)
    if fs_match:
        arr_start = text.index('[', fs_match.start())
        arr_end = _find_matching_bracket(text, arr_start)
        if arr_end > arr_start:
            try:
                arr_text = text[arr_start:arr_end+1]
                arr_text = _fix_json_string_chars(arr_text)
                result["foreshadowing"] = json.loads(arr_text)
            except Exception:
                pass
    # 提取title
    title_match = re.search(r'"title"\s*:\s*"([^"]+)"', text)
    if title_match:
        result["title"] = title_match.group(1)
    return result if result else None


def _find_matching_bracket(text: str, start: int) -> int:
    """找到与text[start]匹配的右括号位置"""
    open_ch = text[start]
    close_ch = ']' if open_ch == '[' else '}'
    depth = 0
    in_str = False
    for i in range(start, len(text)):
        ch = text[i]
        if ch == '"' and (i == 0 or text[i-1] != '\\'):
            in_str = not in_str
        if in_str:
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
    return -1


class NovelEngine:
    def __init__(self, platform: str | None = None):
        # 平台决定字数区间与正文/结构规范（见 app/config/platforms.py）
        self.platform = pf.platform_key(platform)
        self.planner = PlannerAgent()
        self.writer = WriterAgent()
        self.reviewer = ReviewerAgent()
        self.reviser = ReviserAgent()
        self.kb = KnowledgeBaseManager()

    def generate_outline(self, synopsis: str, genre: str, target_chapters: int) -> dict:
        trending = self.kb.search_trending_features(genre)
        trending_str = json.dumps(trending, ensure_ascii=False) if trending else ""
        outline_text = self.planner.plan(
            synopsis, genre, target_chapters, trending_str, platform=self.platform
        )
        outline = _robust_json_parse(outline_text)
        if outline.get("parse_error"):
            logger.warning(f"大纲JSON解析失败，使用容错结果: {str(outline_text)[:200]}")
        return outline

    def generate_chapter(self, chapter_plan: dict, previous_summary: str = "", character_states: str = "", foreshadowing_list: str = "", previous_tail: str = "") -> tuple[str, str]:
        chapter_plan_str = json.dumps(chapter_plan, ensure_ascii=False)
        draft = self.writer.write_chapter(
            chapter_plan_str,
            previous_summary,
            character_states,
            foreshadowing_list,
            previous_tail=previous_tail,
            platform=self.platform,
        )
        model_name = "unknown"
        try:
            from app.services.model_manager import ModelManager
            model = ModelManager().get_model_for_role("writer")
            if model:
                model_name = model.name
        except Exception:
            pass
        return draft, model_name

    def review_and_revise(self, chapter_content: str, chapter_plan: dict, character_states: str = "") -> tuple[str, str, float]:
        chapter_plan_str = json.dumps(chapter_plan, ensure_ascii=False)
        review_text = self.reviewer.review(chapter_content, chapter_plan_str, character_states)
        review_result = _robust_json_parse(review_text)
        score = review_result.get("score", 0) if not review_result.get("parse_error") else 50
        if review_result.get("parse_error"):
            logger.warning(f"审核JSON解析失败，使用默认分数50: {str(review_text)[:200]}")

        current_content = chapter_content
        rounds = 0
        while score < REVIEW_PASS_THRESHOLD and rounds < MAX_REVISION_ROUNDS:
            logger.info(f"章节评分{score}低于阈值{REVIEW_PASS_THRESHOLD}，开始第{rounds + 1}轮修订")
            current_content = self.reviser.revise(
                current_content, json.dumps(review_result, ensure_ascii=False), platform=self.platform
            )
            review_text = self.reviewer.review(current_content, chapter_plan_str, character_states)
            review_result = _robust_json_parse(review_text)
            score = review_result.get("score", 0) if not review_result.get("parse_error") else 50
            rounds += 1

        # spec 5.1.1 规则 6：事实核查 - 检测角色状态一致性，发现矛盾则强制重写
        consistency = review_result.get("consistency_check", {}) if isinstance(review_result, dict) else {}
        if isinstance(consistency, dict) and not consistency.get("character_consistent", True):
            logger.warning(f"检测到角色状态不一致: {consistency}，触发强制重写")
            revise_prompt = f"角色状态一致性检查未通过：{json.dumps(consistency, ensure_ascii=False)}\n请基于章节规划重写，确保角色状态与前文一致。"
            current_content = self.reviser.revise(current_content, revise_prompt, platform=self.platform)

        review_comment = json.dumps(review_result, ensure_ascii=False) if isinstance(review_result, dict) else review_text
        return current_content, review_comment, score

    def write_chapter_with_review(
        self,
        chapter_plan: dict,
        previous_summary: str = "",
        character_states: str = "",
        foreshadowing_list: str = "",
        previous_tail: str = "",
        progress_callback=None,
        ch_num: int | None = None,
        total: int | None = None,
    ) -> dict:
        """写一章的完整链路：初稿 → 审核 → 修订。

        抽成独立方法是为了让 **首批生成** 与 **日更续写** 共用同一条实现。
        历史上这两处各写了一份，上下文规格与去AI化策略都不一致，
        结果就是"首批还行、往后越写越散"。
        """
        num = ch_num if ch_num is not None else chapter_plan.get("number")
        if progress_callback:
            progress_callback(num, total or 1, "writer", f"正在生成第{num}章初稿")
        draft, model_name = self.generate_chapter(
            chapter_plan, previous_summary, character_states, foreshadowing_list, previous_tail
        )
        if progress_callback:
            progress_callback(num, total or 1, "reviewer", f"正在审核修订第{num}章")
        final_content, review_comment, score = self.review_and_revise(
            draft, chapter_plan, character_states
        )
        # 字数兜底：LLM 修订常把正文改得越来越长，光靠 prompt 约束不可靠
        final_content = self._enforce_word_limit(final_content, num)
        return {
            "chapter_number": num,
            "title": chapter_plan.get("title", f"第{num}章"),
            "content": final_content,
            "original_content": draft,
            "model_used": model_name,
            "review_score": score,
            "review_comment": review_comment,
        }

    def _enforce_word_limit(self, content: str, ch_num, max_attempts: int = 3) -> str:
        """确保正文落在平台字数区间 [lo, hi] 内。

        上限：番茄超 2200 就跌出黄金区间、完读率下滑，所以按平台真实上限判定，
              不再放 10% 容差。
        下限：番茄低于 1800 直接判"水文"降权，实测首批 3 章里有 2 章偏短
              （1651 / 1764 字），因此下限和上限一样要显式兜。

        两个方向都由 max_attempts 限次，不会无限烧 token。
        补写仅做"场景内加厚"，严禁新增情节（见 ReviserAgent.expand_to_length）。
        长度口径见 count_words()。
        """
        lo, hi = pf.chapter_words_of(self.platform)
        cur = content or ""

        for i in range(max_attempts):
            n = count_words(cur)
            if n <= hi:
                break
            logger.info(f"第{ch_num}章正文 {n} 字超出平台上限 {hi}（平台={self.platform}），第{i + 1}次压缩")
            try:
                trimmed = self.reviser.trim_to_length(cur, hi, platform=self.platform)
            except Exception as e:
                logger.warning(f"第{ch_num}章压缩失败，保留原稿: {e}")
                break
            if not trimmed or not trimmed.strip():
                break
            cur = trimmed.strip()

        prev_len: int | None = None
        for i in range(max_attempts):
            n = count_words(cur)
            if n >= lo:
                break
            logger.info(f"第{ch_num}章正文 {n} 字低于平台下限 {lo}（平台={self.platform}），第{i + 1}次补写")
            try:
                expanded = self.reviser.expand_to_length(
                    cur, n, platform=self.platform, last_attempt_len=prev_len
                )
            except Exception as e:
                logger.warning(f"第{ch_num}章补写失败，保留原稿: {e}")
                break
            if not expanded or not expanded.strip():
                break
            candidate = expanded.strip()
            # 补写可能一次性冲过上限：撞上限就再压回来，避免"补完变超长"
            if count_words(candidate) > hi:
                try:
                    candidate = (self.reviser.trim_to_length(candidate, hi, platform=self.platform) or candidate).strip()
                except Exception:
                    pass
            cand_n = count_words(candidate)
            # 只接受有增量的候选。
            # 实测模型偶尔会"补"出更短的文本（1747 → 1700），
            # 早期实现在这里直接把劣化结果收下了 → 交付了一章不到下限的正文。
            # 现在改为：不涨就地丢弃、把本轮长度回喂给下一轮继续催。
            if cand_n <= n:
                logger.warning(f"第{ch_num}章第{i + 1}次补写无增量（{n} → {cand_n} 字），丢弃并重试")
                prev_len = n
                continue
            logger.info(f"第{ch_num}章补写进展：{n} → {cand_n} 字")
            prev_len = n
            cur = candidate

        n = count_words(cur)
        if lo <= n <= hi:
            logger.info(f"第{ch_num}章字数合规：{n} 字（平台区间 {lo}-{hi}）")
        elif n > hi:
            logger.warning(f"第{ch_num}章压缩后仍为 {n} 字（上限 {hi}），按现状交付")
        else:
            logger.warning(f"第{ch_num}章补写后仍为 {n} 字（下限 {lo}），按现状交付")
        return cur

    def generate_full_novel(self, synopsis: str, genre: str, target_chapters: int, initial_chapters: int = None, progress_callback=None) -> dict:
        outline = self.generate_outline(synopsis, genre, target_chapters)
        chapters_data = outline.get("chapters", [])
        characters = outline.get("characters", [])
        foreshadowing = outline.get("foreshadowing", [])
        results = []
        character_states = json.dumps(characters, ensure_ascii=False)
        active_foreshadowing = []
        write_count = initial_chapters or len(chapters_data)
        total = len(chapters_data) if chapters_data else target_chapters
        overdue_warnings = []
        # 已写章节，用于给下一章构建衔接上下文（前文脉络 + 上一章正文尾部）
        history: list[dict] = []

        for idx, chapter_plan in enumerate(chapters_data[:write_count], 1):
            ch_num = chapter_plan.get("number", idx)
            logger.info(f"正在生成第{ch_num}章...")

            for fs in foreshadowing:
                if fs.get("planted_chapter") == ch_num:
                    active_foreshadowing.append(fs.get("description", ""))

            # spec 5.1.1 规则 5：伏笔超期告警（超过 5 章未推进）
            for fs in foreshadowing:
                planted = fs.get("planted_chapter", 0)
                resolved = fs.get("resolved_chapter")
                if planted and not resolved and (ch_num - planted) > 5:
                    warning = f"伏笔[{fs.get('description', '')[:20]}]自第{planted}章埋设后已超{ch_num - planted}章未推进"
                    overdue_warnings.append(warning)
                    logger.warning(warning)

            fs_str = json.dumps(active_foreshadowing, ensure_ascii=False) if active_foreshadowing else ""
            previous_summary, previous_tail = build_continuation_context(chapters_data, history)
            result = self.write_chapter_with_review(
                chapter_plan=chapter_plan,
                previous_summary=previous_summary,
                character_states=character_states,
                foreshadowing_list=fs_str,
                previous_tail=previous_tail,
                progress_callback=progress_callback,
                ch_num=ch_num,
                total=total,
            )

            active_foreshadowing = [
                fs for fs in active_foreshadowing
                if not any(f.get("description") == fs and f.get("resolved_chapter") == ch_num for f in foreshadowing)
            ]

            history.append({
                "chapter_number": ch_num,
                "title": result["title"],
                "content": result["content"],
            })
            results.append(result)

        return {
            "outline": outline,
            "chapters": results,
            "overdue_warnings": overdue_warnings,
        }