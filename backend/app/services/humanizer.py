import re
import json
import math
import logging
from typing import Optional
from collections import Counter

logger = logging.getLogger(__name__)

NOVEL_FORBIDDEN_PATTERNS = [
    (r"值得注意的是", "需要关注的是"),
    (r"不仅如此", "而且"),
    (r"总而言之", "总之"),
    (r"毫无疑问", "肯定"),
    (r"不可否认", "确实"),
    (r"众所周知", "大家都知道"),
    (r"显而易见", "明摆着"),
    (r"综上所述", "所以"),
    (r"与此同时", "同时"),
    (r"在当今社会", "现在"),
    (r"随着.*的发展", "现在"),
    (r"发挥了重要作用", "很关键"),
    (r"具有重要意义", "很重要"),
    (r"产生了深远影响", "影响很大"),
    (r"引起了广泛关注", "很多人关注"),
    (r"面临着前所未有的", "遇到了"),
    (r"在.*方面", "在"),
    (r"进行.*研究", "研究"),
    (r"开展.*工作", "做"),
    (r"取得.*成果", "有了结果"),
    (r"一言以蔽之", "总之"),
    (r"不可否认的是", "确实"),
    (r"由此可见", "可见"),
    (r"他感到非常震惊", "他愣住了"),
    (r"她不禁感叹道", "她叹了口气"),
    (r"仿佛.*一般", "像"),
    # v2.0: 小说场景高频AI套话
    (r"不禁微微一笑", "笑了笑"),
    (r"嘴角微微上扬", "嘴角一翘"),
    (r"眼中闪过一丝.*?的光芒", "眼神一变"),
    (r"心中不禁涌起一股", "心里一"),
    (r"仿佛整个世界都", "好像"),
    (r"一股.*?的感觉涌上心头", "心里"),
    (r"深深地吸了一口气", "深吸一口气"),
    (r"缓缓地闭上了眼睛", "闭上眼"),
    (r"不由自主地", "忍不住"),
    (r"情不自禁地", "忍不住"),
    (r"义无反顾地", "毫不犹豫"),
    (r"毫不犹豫地", "直接"),
    (r"如同一把利刃", "像刀子"),
    (r"宛如.*?一般", "像"),
    (r"恰似.*?般", "像"),
    (r"犹如.*?般", "像"),
    (r"心中暗自思忖", "心想"),
    (r"暗自下定决心", "打定主意"),
    (r"目光如炬", "眼神锐利"),
    (r"身姿挺拔如松", "站得笔直"),
    (r"声音低沉而富有磁性", "嗓音低沉"),
    (r"眉宇间透着", "眉间带着"),
    (r"眼中满是.*?之色", "眼里全是"),
    (r"脸上浮现出.*?的神色", "脸上露出"),
    (r"嘴角勾起一抹.*?的弧度", "嘴角一弯"),
    (r"一股.*?的气息扑面而来", "迎面"),
    (r"仿佛时间在这一刻静止", "时间好像停了"),
    (r"空气仿佛凝固了", "空气像冻住了"),
    (r"心中五味杂陈", "心里说不清什么滋味"),
    (r"心中百感交集", "心里翻江倒海"),
    (r"一种.*?的感觉油然而生", "忽然觉得"),
    (r"不禁.*?了起来", "忍不住"),
    # ===== v2.3（2026-09-14 重新调研后新增）=====
    # 类别A：说明文连词（AI 写小说时残留的议论文骨架，网文里几乎不出现）
    (r"然而，?", "可"),
    (r"因此，?", "所以"),
    (r"于是，?", "就"),
    (r"随后，?", "接着"),
    (r"紧接着，?", ""),
    (r"与此同时，?", "同时"),
    (r"除此之外，?", ""),
    (r"此外，?", ""),
    (r"总而言之，?", "总之"),
    (r"换言之，?", "就是说"),
    # 类别B：程度副词堆砌（AI 靠副词加力，人类靠动词和细节）
    (r"非常(?:地)?", ""),
    (r"极其(?:地)?", ""),
    (r"十分(?![钟点])", ""),  # 负向断言：避免误伤“二十分钟”“五十分钟”
    (r"格外(?:地)?", ""),
    (r"无比(?:地)?", ""),
    (r"异常(?:地)?", ""),
    (r"极度(?:地)?", ""),
    # 类别C：翻译腔 / 名词化（"对……进行……"式书面语）
    (r"对(.*?)进行(?:了)?(?:了)?", r"\1"),
    (r"在.*?的过程中", "…的时候"),
    (r"在.*?的情况下", "…的时候"),
    (r"作出(?:了)?(?:一个)?决定", "决定"),
    (r"进行了(?:一次)?", ""),
    # 类别D：全知视角的"只见/只听得"（AI 切镜头的机械腔）
    (r"只见", ""),
    (r"只听得", "听见"),
    (r"不由得", "忍不住"),
    (r"不由得一?愣", "愣住"),
    # 类别E：情绪平滑的"万能过渡"
    (r"不知过了多久", "过了好一会儿"),
    (r"时间一分一秒地过去", "时间一点点过去"),
    (r"空气安静了几秒", "没人说话"),
    (r"气氛一下子尴尬了", "谁都没接话"),
]

# ===== v2.3：番茄小说平台规则（调研自 2026 番茄短篇爆款方法论）=====
# 用于人化改写时的"节奏底线"，不参与正则替换，参与提示词与评分。
FANQIE_RHYTHM_RULES = """
【番茄平台的节奏底线——必须满足】
1. 前 300 字必须出事：冲突当场爆发。删掉天气、起床、身世介绍、世界观铺垫。
2. 每 500-800 字一个钩子（悬念／反常／信息差／一句让人想往下看的话）。
3. 憋屈不超过两章，受委屈→打脸的间隔要短。
4. 能用对话交代的，一律不用旁白交代。
5. 章末必须停在"悬在半空"的地方，不要收尾、不要解释、不要补设定。
"""

# ===== v2.3：感官失衡词表（AI 只调视觉+听觉，缺嗅觉/触觉/温度）=====
SENSE_LEXICON = {
    "smell": ["味", "气味", "腥", "霉", "香", "臭", "烟味", "酸", "呛"],
    "touch": ["烫", "凉", "冷", "冰", "热", "粗糙", "滑", "硬", "软", "扎", "痒", "麻", "黏", "湿", "干"],
    "mouth": ["苦", "甜", "涩", "咸", "腥", "口干", "舌", "牙", "咬"],
    "body": ["后背", "后颈", "头皮", "胃", "喉", "腿软", "手抖", "耳鸣", "喘", "汗", "鸡皮疙瘩"],
}

# ===== v2.3：口语毛边词表（真人稿的"不完美"标记）=====
ORAL_MARKERS = ["就", "嘛", "呗", "得了", "反正", "其实", "说白了", "你懂", "行吧", "算了",
                "啧", "呵", "哈", "唉", "哎", "嗯", "啊", "喂", "靠", "我去", "不是",
                "我操", "真的", "别", "要不", "得亏", "管他"]


class Humanizer:
    def __init__(self):
        self.patterns = [(re.compile(p), r) for p, r in NOVEL_FORBIDDEN_PATTERNS]

    def replace_forbidden_patterns(self, text: str) -> tuple[str, int]:
        count = 0
        result = text
        for pattern, replacement in self.patterns:
            new_result, n = pattern.subn(replacement, result)
            count += n
            result = new_result
        return result, count

    def humanize_quick(self, text: str) -> dict:
        step1, count = self.replace_forbidden_patterns(text)
        step2 = self._inject_sentence_rhythm(step1)
        step3 = self._break_paragraph_templates(step2)
        return {
            "text": step3,
            "strategy": "quick",
            "patterns_replaced": count,
        }

    async def humanize_default(self, text: str, platform: str = "fanqie") -> dict:
        step1_result, count = self.replace_forbidden_patterns(text)
        step1_result = self._inject_sentence_rhythm(step1_result)
        from app.services.model_manager import ModelManager
        mgr = ModelManager()
        system_prompt = self._build_humanize_prompt(platform)
        rewritten = mgr.call_llm(
            prompt=f"请将以下小说文本改写为更像人类手稿的风格（保持剧情、人物、关键事件不变，只改表达方式）：\n\n{step1_result}",
            role="humanizer",
            system_prompt=system_prompt,
            temperature=0.88,
            max_tokens=8192,
        )
        rewritten = self._inject_sentence_rhythm(rewritten)
        return {
            "text": rewritten,
            "strategy": "default",
            "patterns_replaced": count,
            "llm_rewritten": True,
        }

    # ===== v2.3：统一的人化提示词构造器（调研自番茄爆款方法论 + Wikipedia Signs of AI writing）=====
    @staticmethod
    def _build_humanize_prompt(platform: str = "fanqie") -> str:
        platform_block = FANQIE_RHYTHM_RULES if platform == "fanqie" else ""
        return f"""你在替一位写手改稿。稿子读起来太"顺"、太"整齐"，一眼能看出是模型写的。你的活儿是把它改到像人熬夜写出来的。
{platform_block}
【只能动表达，不能动事实】
- 情节、人物、关系、时间地点、关键物件、数字、结局，一个字都不能改。
- 不许自己加情节、加人物、加反转。你只换说法。

【去 AI 味的十二条硬指标】
1. 砍长句。原文任何超过 25 字的句子，拆成 2-3 个短句。真人写网文，一句平均 12-18 字。
2. 长短要错落。不要全文都是中长句的匀速节奏——连着几个短句砸下去，再垫一个长句。偶尔单独成段的三个字，比一整段描写有劲。
3. 补非视觉感官。这是 AI 最大的破绽：它只写"看到""听到"。每 2-3 段里必须出现一次气味、温度、触感、口腔感觉或身体反应（铁锈味、后颈发凉、手心的汗、牙根发酸、胃往下坠）。
4. 删干净说明文连词。然而、因此、于是、随后、紧接着、与此同时、除此之外、此外、综上所述——一个不留。
5. 删干净程度副词堆砌。非常、极其、十分、格外、无比、异常、极度——全部删掉，改用动词和细节去顶。
6. 去掉翻译腔。不能出现"对……进行……""在……的过程中""作出决定""产生了……的影响"。改成人话。
7. 去掉全知视角的机械腔。"只见""与此同时""他不知道的是"——砍掉。谁在场就只写谁能感知到的东西。
8. 对话要接不住。真人不按剧本说话：会打断、会答非所问、会突然跑题、会把话说一半停住、会用一句"行吧"代替一整段解释。把工整的问答砍成半句。
9. 允许毛边。人写稿是脏的：可以有口语填充（就那个、反正、你懂吧）、自我更正（不对，是……）、不完整的句子、重复的字。别修得太干净。
10. 情绪不要平滑。AI 的情绪是匀速流淌的。人不是——该炸的地方炸，该冷场的地方就一个字都不说。允许莫名的走神、忽然想笑、气过头之后的空白。
11. 抽象换成具体。不写"他很难过"，写"他把烟按灭在烟灰缸边上，按了三次"。
12. 结尾别收口。不要总结、不要升华、不要抒情收束，停在动作或对话上。
{platform_block and "13. 注意上面【番茄平台的节奏底线】，它比文采重要。" or ""}

【绝对禁止】
- 不要输出任何解释、说明、标题、前言、后记、修改说明、字数统计、自我介绍。
- 不要写"以下是改写后的文本"这类话。
- 只输出正文本身。

现在开始改，直接给成品。"""

    async def humanize_deep(self, text: str) -> dict:
        step1_result, count = self.replace_forbidden_patterns(text)
        step1_result = self._inject_sentence_rhythm(step1_result)
        from app.services.model_manager import ModelManager
        mgr = ModelManager()
        translation_chain = ["日语", "芬兰语", "中文"]
        current_text = step1_result
        completed_steps = []
        for target_lang in translation_chain:
            try:
                current_text = mgr.call_llm(
                    prompt=f"请将以下文本翻译成{target_lang}，保持原文意思：\n\n{current_text}",
                    role="humanizer",
                    temperature=0.3,
                )
                completed_steps.append(target_lang)
            except Exception as e:
                logger.warning(f"翻译链步骤[{target_lang}]失败，跳过该步继续: {e}")
                continue
        if not completed_steps:
            logger.error("翻译链所有步骤均失败，回退到原文")
            current_text = step1_result
        else:
            logger.info(f"翻译链完成步骤: {completed_steps}")
        system_prompt = """你是一位资深文学编辑，请将以下经过翻译链处理的文本进行最终润色：
1. 修正翻译中可能出现的语义偏差
2. 确保中文表达自然流畅
3. 保持核心剧情不变
4. 增加文学性和可读性"""
        try:
            final_text = mgr.call_llm(
                prompt=f"请润色以下文本：\n\n{current_text}",
                role="humanizer",
                system_prompt=system_prompt,
                temperature=0.7,
            )
        except Exception as e:
            logger.warning(f"最终润色失败，使用翻译链结果: {e}")
            final_text = current_text
        final_text = self._inject_sentence_rhythm(final_text)
        return {
            "text": final_text,
            "strategy": "deep",
            "patterns_replaced": count,
            "translation_chain": completed_steps,
            "translation_degraded": len(completed_steps) < len(translation_chain),
            "llm_rewritten": True,
            "deprecated": True,
        }

    async def humanize_recursive(
        self, text: str, rounds: int = 3, n_candidates: int = 3, platform: str = "fanqie"
    ) -> dict:
        step1_result, count = self.replace_forbidden_patterns(text)
        step1_result = self._inject_sentence_rhythm(step1_result)
        from app.services.model_manager import ModelManager
        mgr = ModelManager()

        score_before = self._statistical_ai_score_v2(step1_result)
        logger.info(
            f"递归释义开始: 平台={platform}, 原始AI分数={score_before}, "
            f"计划{rounds}轮×{n_candidates}候选"
        )

        # 2026-09-14 平台化：复用统一的人化提示词（含目标平台的节奏底线），
        # 再追加 Best-of-N 多轮特有的多样性要求。
        system_prompt = self._build_humanize_prompt(platform) + """

【本策略的多轮补充要求】
- 同一片段会被改写多轮，每轮换一种手感，不要反复使用同一套句式和口头禅。
- 保持原文核心剧情、人物关系、关键事件完全不变，只改表达方式。
- 直接输出改写后的完整文本，不要任何前缀说明、后缀解释、元评论、自我介绍或对改写过程的描述。"""

        current_text = step1_result
        rounds_completed = 0
        best_overall_text = step1_result
        best_overall_score = score_before

        for round_idx in range(rounds):
            logger.info(f"递归释义第{round_idx + 1}/{rounds}轮开始")
            candidates = []
            for cand_idx in range(n_candidates):
                try:
                    candidate = mgr.call_llm(
                        prompt=f"请改写以下小说片段：\n\n{current_text}\n\n直接输出改写后的完整文本，不要任何说明、解释或评论。",
                        role="humanizer",
                        system_prompt=system_prompt,
                        temperature=0.8 + cand_idx * 0.05,
                        # 2026-09-15 修复：这里原先没传 max_tokens，落到 call_llm 默认的 4096。
                        # 但本策略要求"输出完整改写后的全文"，输出长度≈输入长度，
                        # 2000 字正文很容易把 4096 token 用光 → 结尾被硬切 →
                        # 一致性检查每次都判"结尾截断/关键剧情缺失" → 候选全被跳过 →
                        # 文本一轮都没改成（用户反馈的"处理前后计数不变"就是这个）。
                        # 同文件的 humanize_default / humanize_adversarial 都传了 8192，此处对齐。
                        max_tokens=8192,
                    )
                    candidate = self._inject_sentence_rhythm(candidate)
                    # 长度地板：即便一致性检查放行，也绝不接受一份明显被截断的稿子
                    if len(candidate) < len(current_text) * 0.8:
                        logger.warning(
                            f"第{round_idx + 1}轮候选{cand_idx + 1}疑似截断"
                            f"（{len(current_text)} → {len(candidate)} 字），丢弃"
                        )
                        continue
                    # 结尾完整性：正文末尾必须是句读（。！？…"』」）。
                    # 长度地板拦不住"只少十几个字"的截断 —— 实测第10章被切在
                    # "那里，还"（少了一句收尾），字数仍有原稿的 83.7%，顺利混过长度检查，
                    # 直到导出成品时才在文件末尾暴露出来。句读检查才是最直接的判据。
                    # 字符集必须带上全角引号 ” ’ —— 对话收尾的正文是以 ” 结束的，
                    # 漏掉会把"……微笑。”这类正常结尾误判成截尾、白白丢弃好候选。
                    if not re.search(r"[。！？…\.\!\?\"'”’』」）\)】]$", candidate.strip()):
                        logger.warning(
                            f"第{round_idx + 1}轮候选{cand_idx + 1}结尾无句读、疑似截尾"
                            f"（末尾：…{candidate.strip()[-20:]}），丢弃"
                        )
                        continue
                    candidates.append(candidate)
                except Exception as e:
                    logger.warning(f"第{round_idx + 1}轮候选{cand_idx + 1}生成失败: {e}")
                    continue

            if not candidates:
                logger.warning(f"第{round_idx + 1}轮所有候选生成失败，降级到原文继续")
                continue

            best_candidate = None
            best_cand_score = float("inf")
            for candidate in candidates:
                try:
                    consistency = self.check_consistency(step1_result, candidate)
                    if not consistency.get("consistent", False):
                        logger.info(f"候选一致性检查未通过，跳过: {consistency.get('issues', [])}")
                        continue
                    cand_score = self._statistical_ai_score_v2(candidate)
                    if cand_score < best_cand_score:
                        best_cand_score = cand_score
                        best_candidate = candidate
                except Exception as e:
                    logger.warning(f"候选评分失败: {e}")
                    continue

            if best_candidate is None:
                logger.warning(f"第{round_idx + 1}轮无候选通过一致性检查，保留当前文本继续")
                continue

            current_text = best_candidate
            if best_cand_score <= best_overall_score:
                best_overall_score = best_cand_score
                best_overall_text = best_candidate
            rounds_completed += 1
            logger.info(f"第{round_idx + 1}轮完成: 本轮最优={best_cand_score:.1f}, 全局最优={best_overall_score:.1f}")

        if rounds_completed == 0:
            logger.error("递归释义所有轮次失败，降级返回原文")
            return {
                "text": step1_result,
                "strategy": "recursive",
                "patterns_replaced": count,
                "rounds_completed": 0,
                "score_before": score_before,
                "score_after": score_before,
                "degraded": True,
                "llm_rewritten": False,
            }

        return {
            "text": best_overall_text,
            "strategy": "recursive",
            "patterns_replaced": count,
            "rounds_completed": rounds_completed,
            "score_before": score_before,
            "score_after": best_overall_score,
            "degraded": False,
            "llm_rewritten": True,
        }

    # v2.0: 对抗性改写（Adversarial Paraphrasing，arXiv:2506.07001）
    async def humanize_adversarial(self, text: str, max_rounds: int = 5, platform: str = "fanqie") -> dict:
        """检测器反馈引导的对抗性改写：改写→评分→反馈→再改写，直到分数足够低"""
        step1_result, count = self.replace_forbidden_patterns(text)
        step1_result = self._inject_sentence_rhythm(step1_result)

        from app.services.model_manager import ModelManager
        mgr = ModelManager()

        score_before = self._statistical_ai_score_v2(step1_result)
        current_text = step1_result
        best_text = step1_result
        best_score = score_before
        history = []

        for round_idx in range(max_rounds):
            score_current = self._statistical_ai_score_v2(current_text)
            # v2.1: 第1轮必须执行（即使统计分数低，LLM改写才能真正降低真实检测器的分数）
            if round_idx > 0 and score_current <= 25.0:
                logger.info(f"对抗性改写第{round_idx + 1}轮: 分数已降至{score_current:.1f}，达标退出")
                break

            diagnosis = self._diagnose_ai_signals(current_text)
            feedback = self._build_adversarial_feedback(diagnosis, score_current)

            system_prompt = f"""{self._build_humanize_prompt(platform)}

【本轮额外任务】上一版稿子的 AI 检测分为 {score_current:.1f}/100（越低越像人）。下面是机器诊断出来的具体毛病，逐条改掉：

{feedback}"""

            try:
                rewritten = mgr.call_llm(
                    prompt=f"请改写以下小说片段：\n\n{current_text}",
                    role="humanizer",
                    system_prompt=system_prompt,
                    temperature=0.9,
                    max_tokens=8192,
                )
                rewritten = self._inject_sentence_rhythm(rewritten)
            except Exception as e:
                logger.warning(f"对抗性改写第{round_idx + 1}轮失败: {e}")
                continue

            consistency = self.check_consistency(step1_result, rewritten)
            if not consistency.get("consistent", False):
                logger.warning(f"对抗性改写第{round_idx + 1}轮一致性检查未通过，跳过")
                continue

            new_score = self._statistical_ai_score_v2(rewritten)
            history.append({"round": round_idx + 1, "score_before": score_current, "score_after": new_score, "diagnosis": diagnosis})

            if new_score < best_score:
                best_score = new_score
                best_text = rewritten
            current_text = rewritten
            logger.info(f"对抗性改写第{round_idx + 1}轮: {score_current:.1f} -> {new_score:.1f}, 全局最优={best_score:.1f}")

        return {
            "text": best_text,
            "strategy": "adversarial",
            "patterns_replaced": count,
            "score_before": score_before,
            "score_after": best_score,
            "rounds_completed": len(history),
            "history": history,
            "degraded": best_score >= score_before,
            "llm_rewritten": True,
        }

    async def humanize(self, text: str, strategy: str = "default", platform: str = "fanqie") -> dict:
        if strategy == "quick":
            return self.humanize_quick(text)
        elif strategy == "deep":
            logger.warning("deep 策略已弃用（v1.3.0），建议使用 adversarial 策略")
            return await self.humanize_deep(text)
        elif strategy == "recursive":
            return await self.humanize_recursive(text, platform=platform)
        elif strategy == "adversarial":
            return await self.humanize_adversarial(text, platform=platform)
        else:
            return await self.humanize_default(text, platform=platform)

    # ========== v2.0: 多维统计评分（替代 LLM 自评为主评分） ==========

    def evaluate_ai_score(self, text: str) -> float:
        """v2.0: 以统计评分为主（权重0.7），LLM自评为辅（权重0.3）。
        修复：旧版LLM自评权重0.7导致评分虚高（LLM天然倾向判AI）。
        """
        stat_score = self._statistical_ai_score_v2(text)
        try:
            from app.services.model_manager import ModelManager
            mgr = ModelManager()
            llm_score = self._llm_ai_score(mgr, text)
            mixed = stat_score * 0.7 + llm_score * 0.3
            logger.debug(f"AI检测评分v2: 统计={stat_score:.1f}, LLM={llm_score:.1f}, 混合={mixed:.1f}")
            return round(mixed, 1)
        except Exception as e:
            logger.warning(f"LLM自评不可用，降级为纯统计评分: {e}")
            return round(stat_score, 1)

    def _statistical_ai_score_v2(self, text: str) -> float:
        """v2.0: 多维统计评分，参考 arXiv 检测器特征 + stephenlzc/humanize-mba-text-skill"""
        score = 0.0

        # 维度1: 套话命中（0-20分）
        pattern_hits = sum(1 for p, _ in self.patterns if p.search(text))
        score += min(pattern_hits * 3.0, 20.0)

        # 维度2: 句长CV（0-25分，CV越低越像AI）
        cv = self._compute_sentence_cv(text)
        if cv < 0.25:
            score += 25.0
        elif cv < 0.35:
            score += 18.0
        elif cv < 0.45:
            score += 10.0
        elif cv < 0.55:
            score += 5.0
        else:
            score += 0.0

        # 维度3: 词汇多样性 TTR（0-15分）
        ttr = self._compute_ttr(text)
        if ttr < 0.3:
            score += 15.0
        elif ttr < 0.4:
            score += 10.0
        elif ttr < 0.5:
            score += 5.0
        else:
            score += 0.0

        # 维度4: 平均句长（0-15分）
        sentences = self._split_sentences(text)
        if sentences:
            avg_len = sum(len(s) for s in sentences) / len(sentences)
            if avg_len > 40:
                score += 15.0
            elif avg_len > 30:
                score += 10.0
            elif avg_len > 25:
                score += 5.0

        # 维度5: 段落结构模板化（0-10分）
        template_score = self._detect_paragraph_template(text)
        score += template_score

        # 维度6: 情感一致性（0-10分，AI文本情感过于平稳）
        emotion_score = self._detect_emotion_flatness(text)
        score += emotion_score

        # 维度7: 排比/重复（0-5分）
        parallelism = len(re.findall(r"[，。]\s*([一二三四五六七八九十])[、，]", text))
        repeated = len(re.findall(r"(.)\1{3,}", text))
        score += min(parallelism * 2 + repeated * 1, 5.0)

        # ===== v2.3 新增三维（原始满分 100，新维满分 23，末尾统一归一化到 100）=====
        # 维度8: 感官失衡（0-10分）—— AI 只调视觉/听觉，缺气味、温度、触感、身体反应
        sense_cats = sum(1 for words in SENSE_LEXICON.values() if any(w in text for w in words))
        if sense_cats == 0:
            score += 10.0
        elif sense_cats == 1:
            score += 6.0
        elif sense_cats == 2:
            score += 3.0

        # 维度9: 赘余副词/说明文连词残余（0-8分）
        leftover = re.findall(
            r"非常|极其|十分(?![钟点])|格外|无比|然而|因此|于是|只见|不由得|与此同时|除此之外|此外|"
            r"对[^，。]{1,8}进行|在[^，。]{1,8}的过程中|不禁|不由自主|缓缓地|轻轻地|微微地",
            text,
        )
        score += min(len(leftover) * 1.0, 8.0)

        # 维度10: 口语毛边缺失（0-5分）—— 真人稿有语气词、口头禅、半截话
        oral_hits = sum(text.count(w) for w in ORAL_MARKERS)
        oral_density = oral_hits / max(len(re.findall(r"[。！？]", text)), 1)
        if oral_density < 0.1:
            score += 5.0
        elif oral_density < 0.25:
            score += 2.5

        return round(min(max(score / 123.0 * 100.0, 0.0), 100.0), 1)

    def _statistical_ai_score(self, text: str) -> float:
        """旧版评分（兼容）"""
        return self._statistical_ai_score_v2(text)

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        return [s.strip() for s in re.split(r"[。！？\n]+", text) if s.strip()]

    def _compute_sentence_cv(self, text: str) -> float:
        """句长变异系数。CV < 0.30 = AI特征（句子长度过于均匀）"""
        sentences = self._split_sentences(text)
        if len(sentences) < 3:
            return 0.5
        lengths = [len(s) for s in sentences]
        mean = sum(lengths) / len(lengths)
        if mean == 0:
            return 0.5
        variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
        std = math.sqrt(variance)
        return std / mean

    @staticmethod
    def _compute_ttr(text: str) -> float:
        """Type-Token Ratio 词汇多样性。TTR低 = AI特征（偏好高频词）"""
        chars = [c for c in text if '\u4e00' <= c <= '\u9fff']
        if len(chars) < 10:
            return 0.5
        bigrams = [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]
        if not bigrams:
            return 0.5
        return len(set(bigrams)) / len(bigrams)

    def _detect_paragraph_template(self, text: str) -> float:
        """段落结构模板化检测（0-10分）"""
        score = 0.0
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) < 3:
            return 0.0
        # 段落长度均匀度
        para_lens = [len(p) for p in paragraphs]
        if para_lens:
            mean_pl = sum(para_lens) / len(para_lens)
            if mean_pl > 0:
                var_pl = sum((l - mean_pl) ** 2 for l in para_lens) / len(para_lens)
                cv_pl = math.sqrt(var_pl) / mean_pl
                if cv_pl < 0.2:
                    score += 5.0
                elif cv_pl < 0.3:
                    score += 3.0
        # 段首重复模式
        starts = [p[:4] for p in paragraphs if len(p) >= 4]
        if starts:
            start_counter = Counter(starts)
            max_repeat = start_counter.most_common(1)[0][1] if start_counter else 0
            if max_repeat >= 3:
                score += 5.0
            elif max_repeat >= 2:
                score += 2.0
        return min(score, 10.0)

    @staticmethod
    def _detect_emotion_flatness(text: str) -> float:
        """情感一致性检测（0-10分，AI文本情感过于平稳）"""
        emotion_words = {
            "喜": ["笑", "喜", "乐", "欢", "悦"],
            "怒": ["怒", "愤", "恨", "气", "恼"],
            "哀": ["哭", "悲", "哀", "伤", "痛"],
            "惧": ["怕", "惧", "恐", "惊", "慌"],
        }
        emotion_counts = {}
        for cat, words in emotion_words.items():
            emotion_counts[cat] = sum(text.count(w) for w in words)
        total = sum(emotion_counts.values())
        if total == 0:
            return 3.0
        categories_present = sum(1 for v in emotion_counts.values() if v > 0)
        if categories_present <= 1:
            return 8.0
        elif categories_present <= 2:
            return 5.0
        elif categories_present <= 3:
            return 2.0
        return 0.0

    # ========== v2.0: 句长节奏注入 ==========

    def _inject_sentence_rhythm(self, text: str) -> str:
        """对句长CV<0.40的段落，在长句中插入短句断点，提高节奏变化。
        不删除或移动句号，只在逗号处添加句号断点。"""
        paragraphs = text.split("\n\n")
        result = []
        for para in paragraphs:
            if not para.strip():
                result.append(para)
                continue
            cv = self._compute_sentence_cv(para)
            if cv >= 0.40:
                result.append(para)
                continue
            modified = self._add_rhythm_breaks(para)
            result.append(modified)
        return "\n\n".join(result)

    @staticmethod
    def _add_rhythm_breaks(para: str) -> str:
        """在过长句子的逗号处添加句号断点，增加句长变化。"""
        sentences = re.split(r"([。！？])", para)
        result = []
        for i, part in enumerate(sentences):
            if len(part) > 50 and "，" in part:
                clauses = part.split("，")
                mid = len(clauses) // 2
                first = "，".join(clauses[:mid]) + "。"
                second = "，".join(clauses[mid:])
                result.append(first)
                result.append(second)
            else:
                if i > 0 and part in "。！？" and result:
                    result[-1] += part
                else:
                    result.append(part)
        return "".join(result)

    @staticmethod
    def _break_paragraph_templates(text: str) -> str:
        """打破段落结构模板"""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) < 3:
            return text
        result = []
        for para in paragraphs:
            if len(para) > 80:
                sents = [s.strip() for s in re.split(r"([。！？])", para) if s.strip()]
                mid = len(sents) // 2
                if mid > 0:
                    first_half = "".join(sents[:mid])
                    second_half = "".join(sents[mid:])
                    result.append(first_half)
                    result.append(second_half)
                    continue
            result.append(para)
        return "\n\n".join(result)

    # ========== v2.0: 对抗性改写诊断 ==========

    def _diagnose_ai_signals(self, text: str) -> dict:
        """诊断文本中的AI信号，返回具体问题列表"""
        issues = []
        cv = self._compute_sentence_cv(text)
        if cv < 0.30:
            issues.append(f"句长过于均匀(CV={cv:.2f})，需要增加长短句交替")
        elif cv < 0.40:
            issues.append(f"句长略显均匀(CV={cv:.2f})，可以再增加节奏变化")
        ttr = self._compute_ttr(text)
        if ttr < 0.4:
            issues.append(f"词汇多样性不足(TTR={ttr:.2f})，需要使用更多低频词和具体描写")
        pattern_hits = [(p.pattern, p.findall(text)) for p, _ in self.patterns if p.search(text)]
        if pattern_hits:
            for pat, matches in pattern_hits[:5]:
                issues.append(f"包含AI套话: {matches[:3]}")
        emotion_score = self._detect_emotion_flatness(text)
        if emotion_score >= 5.0:
            issues.append("情感波动不足，需要增加情感起伏和突变")
        template_score = self._detect_paragraph_template(text)
        if template_score >= 3.0:
            issues.append("段落结构过于模板化，需要变化段落长度和开头方式")

        # ===== v2.3 新增诊断 =====
        sense_cats = sum(1 for words in SENSE_LEXICON.values() if any(w in text for w in words))
        if sense_cats <= 1:
            issues.append("非视觉感官几乎为零（没有气味/温度/触感/身体反应），像在隔着玻璃看画面")
        leftover = re.findall(
            r"非常|极其|十分(?![钟点])|格外|无比|然而|因此|于是|只见|不由得|与此同时|除此之外|此外|"
            r"对[^，。]{1,8}进行|在[^，。]{1,8}的过程中|不禁|不由自主",
            text,
        )
        if leftover:
            issues.append(f"仍残留说明文连词/程度副词 {len(leftover)} 处: {leftover[:6]}")
        oral_hits = sum(text.count(w) for w in ORAL_MARKERS)
        oral_density = oral_hits / max(len(re.findall(r"[。！？]", text)), 1)
        if oral_density < 0.25:
            issues.append(f"口语毛边不足(密度={oral_density:.2f})，文字太干净，缺少口癖、半截话、自我更正")

        return {
            "cv": cv,
            "ttr": ttr,
            "issues": issues,
            "pattern_hits": len(pattern_hits),
            "sense_cats": sense_cats,
            "leftover": len(leftover),
            "oral_density": oral_density,
        }

    @staticmethod
    def _build_adversarial_feedback(diagnosis: dict, score: float) -> str:
        """根据诊断结果构建给LLM的反馈"""
        lines = [f"当前AI检测分数: {score:.1f}/100", ""]
        if diagnosis["issues"]:
            lines.append("检测到以下AI特征问题：")
            for i, issue in enumerate(diagnosis["issues"], 1):
                lines.append(f"  {i}. {issue}")
            lines.append("")
            lines.append("请针对以上问题逐项修复：")
            if diagnosis["cv"] < 0.40:
                lines.append("- 增加长短句交替：在长句中插入3-5字的短句，制造节奏感")
            if diagnosis["ttr"] < 0.4:
                lines.append("- 用更具体、更口语化的词替换抽象描写（如'他感到悲伤'→'他攥紧了拳头，指甲掐进肉里'）")
            if diagnosis["pattern_hits"] > 0:
                lines.append("- 删除所有AI套话词，用自然表达替代")
            if any("情感" in i for i in diagnosis["issues"]):
                lines.append("- 增加情感突变：在平稳叙事中插入突然的情绪爆发或沉默")
            if any("模板" in i for i in diagnosis["issues"]):
                lines.append("- 变化段落长度：有的段落只写一句话，有的段落写满细节")
            # ===== v2.3 新增修复指令 =====
            if diagnosis.get("sense_cats", 0) <= 1:
                lines.append("- 补非视觉感官：挑 3-5 个地方塞进气味（铁锈味/消毒水味/油烟味）、"
                             "温度（后颈发凉/掌心发烫）、触感（指甲掐进肉里）或身体反应（胃往下坠/耳鸣/腿软）")
            if diagnosis.get("leftover", 0) > 0:
                lines.append("- 把残留的'然而/因此/于是/非常/极其/只见/不禁'全部删掉，"
                             "改用动作和细节顶上去，不要用副词加力")
            if diagnosis.get("oral_density", 1.0) < 0.25:
                lines.append("- 加口语毛边：让人物说话带口癖、说半句就停、答非所问；"
                             "叙述里允许出现'反正''就那个''算了'这类不整洁的填充")
            if any("口语" in i for i in diagnosis["issues"]):
                lines.append("- 允许脏稿：可以有重复的字、自我更正（'不对，是……'）、不完整的句子，别改得太干净")
        else:
            lines.append("未检测到明显AI特征，文本质量良好。")
        # ===== v2.3：番茄节奏专项检查 =====
        lines.append("")
        lines.append("【番茄节奏自检——改完必须过这四关】")
        lines.append("1. 开头 300 字内有没有出事？没有冲突就把它挪到最前面。")
        lines.append("2. 通篇有没有 3 个以上让人想往下翻的钩子？不足就补。")
        lines.append("3. 对话占比是不是低于三成？低了就把旁白改成对话。")
        lines.append("4. 结尾是不是收口了？收口就砍掉最后一段总结，停在动作或半句对白上。")
        return "\n".join(lines)

    # ========== LLM 自评（保留但降权） ==========

    @staticmethod
    def _llm_ai_score(mgr, text: str) -> float:
        system_prompt = """你是一个专业的 AI 文本检测器。请评估给定文本被识别为 AI 生成的概率。
只输出一个 0 到 100 之间的数字，不要输出任何其他内容。
评分标准：
- 90-100：高度疑似 AI（套话多、句式工整、缺乏个性）
- 60-89：较像 AI
- 30-59：中性
- 0-29：高度疑似人类写作（口语化、个性化、有细节）"""
        result = mgr.call_llm(
            prompt=f"请评估以下中文文本的 AI 检测分数：\n\n{text[:2000]}",
            role="reviewer",
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=20,
        )
        match = re.search(r"\d+(?:\.\d+)?", result.strip())
        if match:
            score = float(match.group())
            return min(max(score, 0.0), 100.0)
        return 50.0

    # ========== 一致性检查 ==========

    def _extract_keywords_internal(self, text: str) -> set:
        numbers = set(re.findall(r"\d+(?:\.\d+)?", text))
        numbers |= set(re.findall(r"\d+(?:\.\d+)?%", text))
        return numbers

    # 单段送审长度上限。超过则头尾取样，避免把整章几千字全塞给裁判模型。
    CONSISTENCY_SAMPLE_LIMIT = 6000

    @classmethod
    def _sample_for_review(cls, text: str) -> str:
        """给一致性裁判看的文本片段。

        2026-09-15 修复：原先这里传的是 `text[:1500]`，只给裁判看前 1500 字。
        而番茄/百度单章普遍 2000-3000 字，于是裁判拿到的"原文"是被从中间截断的，
        它会据此判"原文在 X 处戛然而止""改写后新增了原文没有的结尾"——
        **这些 issues 全是取样截断的产物，不是稿子的问题**。
        后果就是候选几乎每轮全被拒 → 文本一轮都改不动
        （用户反馈的"处理前后计数不变"根因之一）。

        现在：整章不超过上限就送全文；超长则送"头 4000 + 尾 2000"，
        并显式标注中间省略，避免裁判误判为原文缺失。
        """
        if len(text) <= cls.CONSISTENCY_SAMPLE_LIMIT:
            return text
        head, tail = 4000, 2000
        return f"{text[:head]}\n……（此处省略中间 {len(text) - head - tail} 字）……\n{text[-tail:]}"

    def check_consistency(self, original: str, humanized: str) -> dict:
        orig_kw = self._extract_keywords_internal(original)
        hum_kw = self._extract_keywords_internal(humanized)
        missing = orig_kw - hum_kw
        missing_ratio = len(missing) / len(orig_kw) if orig_kw else 0.0

        try:
            from app.services.model_manager import ModelManager
            mgr = ModelManager()
            system_prompt = """你是剧情一致性审核员。请对比原文和改写后的文本，判断核心剧情和角色设定是否保持一致。
只输出 JSON：{"consistent": true/false, "issues": ["问题描述1", ...]}
判断标准：
- consistent=true：核心剧情、人物关系、关键事件、结局均未改变
- consistent=false：人物性格改变、关键剧情缺失、结局改变、新增情节
注意：
- 改写只允许改表达方式，不允许改剧情。措辞、句式、感官描写的差异不算问题。
- 若文本中出现"此处省略中间 N 字"的标注，那是取样说明，**不是剧情缺失**，不要据此判定不一致。"""
            result = mgr.call_llm(
                # 必须给足篇幅：只送前缀会让裁判把"取样截断"误判成"剧情缺失"
                prompt=(
                    f"原文：\n{self._sample_for_review(original)}\n\n"
                    f"改写后：\n{self._sample_for_review(humanized)}"
                ),
                role="reviewer",
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=500,
            )
            start = result.find("{")
            end = result.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(result[start:end])
                if data.get("consistent") and missing_ratio > 0.5 and len(missing) >= 3:
                    logger.warning(f"LLM判定一致但数字关键词缺失较多({missing_ratio:.0%})：{list(missing)[:5]}")
                return data
        except Exception as e:
            logger.warning(f"LLM一致性检查不可用，降级为关键词比对: {e}")

        consistent = missing_ratio <= 0.3
        return {
            "consistent": consistent,
            "issues": [] if consistent else [f"改写后缺失关键元素：{list(missing)[:5]}"],
        }
