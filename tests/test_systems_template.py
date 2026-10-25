import unittest
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
ASSET_TEMPLATE = REPO_ROOT / "skills" / "paper-reader" / "assets" / "paper-note-template.md"
PAPER_READER_SKILL = REPO_ROOT / "skills" / "paper-reader" / "SKILL.md"
CONCEPT_NOTES_SKILL = REPO_ROOT / "skills" / "concept-notes" / "SKILL.md"
QUALITY_STANDARDS = REPO_ROOT / "skills" / "paper-reader" / "references" / "quality-standards.md"
CONCEPT_CATEGORIES = REPO_ROOT / "skills" / "concept-notes" / "references" / "concept-categories.md"
CONCEPT_TEMPLATE = REPO_ROOT / "skills" / "concept-notes" / "assets" / "concept-note-template.md"
DIAGRAM_RULES = REPO_ROOT / "skills" / "_shared" / "references" / "diagram-rules.md"
REGENERATE_CONCEPTS = REPO_ROOT / "skills" / "concept-notes" / "scripts" / "regenerate_concepts.py"
CONCEPT_LENGTH_RULE = "直观例子 ≤ 100 行、其他段 ≤ 90 行（不计 frontmatter 和图的源码）"


def assert_table_header(testcase, text, columns):
    escaped_columns = [re.escape(column) for column in columns]
    pattern = r"(?m)^\|\s*" + r"\s*\|\s*".join(escaped_columns) + r"\s*\|$"
    testcase.assertRegex(text, pattern)


def heading_index(text, heading):
    """Offset of a heading line; the template's HTML comment also names headings, so anchor at line start."""
    match = re.search(r"(?m)^" + re.escape(heading) + r"\s*$", text)
    assert match is not None, heading
    return match.start()


class SystemsTemplateTests(unittest.TestCase):
    def test_asset_template_uses_systems_sections(self):
        text = ASSET_TEMPLATE.read_text(encoding="utf-8")

        required_sections = [
            "## 这篇论文为什么重要",
            "## 核心贡献",
            "## 问题定义",
            "### 系统范围与层次",
            "### 要解决的问题",
            "### 现有方法与设计空间",
            "## 动机实验与核心 Insights",
            "### Insight 1：",
            "### 设计原则到机制的映射",
            "## 系统设计总览",
            "### 系统架构",
            "### 执行流",
            "### 优化目标与度量口径",
            "## 关键机制拆解",
            "## 实验设置",
            "## 核心结果",
            "## Overhead 与兼容性",
            "### 实现改动清单",
            "## 批判性思考",
            "## 经验与可迁移启示",
            "## 复现",
            "## 关联笔记",
            "## 速查卡片",
        ]
        for section in required_sections:
            self.assertIn(section, text)

        forbidden_sections = [
            "## 关键公式",
            "## 关键图表",
            "## 局限与隐含假设",
            "## 复现与借鉴价值",
            "## 复现线索",
            "### 部署位置",
            "### 数据流 / 控制流",
            "### 关键指标 / 总览公式",
            "### 关键组件",
            "### 硬件改动清单",
            "#### 对应公式 / 图示",
            "#### 参数选择 / 设计空间扫描",
            "### 与实验设置强相关的图 / 公式",
            "### 可复现性评估",
            "## 问题定义与瓶颈",
            "## 作者核心 Insights",
            "## 动机实验 / Characterization",
            "### 系统瓶颈",
            "### 本文的动机",
            "### 特征图与数字证据",
            "### 由实验得到的设计原则",
            "### 系统架构与执行流",
            "### 系统组成与职责",
            "#### 模块关系图",
        ]
        for section in forbidden_sections:
            self.assertNotRegex(text, rf"(?m)^{re.escape(section)}(?:\s|$)")

        self.assertIn("### 实现改动清单", text)
        self.assertIn("#### 参数与权衡", text)
        self.assertIn("### 模拟器与微架构参数", text)
        self.assertIn("#### Silicon-feasibility", text)
        # 自画图默认走 diagram-design 导出 PNG，模板不再内嵌 Mermaid 代码块
        self.assertNotIn("```mermaid", text)
        self.assertIn("![[00_assets/<note-name>_platform.png|", text)
        assert_table_header(self, text, ["组件", "职责", "输入输出", "关键状态或参数", "关联概念"])

    def test_related_work_table_requires_internal_and_external_link_slots(self):
        asset_text = ASSET_TEMPLATE.read_text(encoding="utf-8")

        assert_table_header(self, asset_text, ["论文", "外部链接", "关系", "差异"])
        self.assertIn("`论文` 列优先写", asset_text)
        self.assertIn("`外部链接` 列写", asset_text)

    def test_paper_reader_skill_mentions_systems_specific_requirements(self):
        text = PAPER_READER_SKILL.read_text(encoding="utf-8")

        self.assertIn("Overhead 与兼容性", text)
        self.assertIn("经验与可迁移启示", text)
        self.assertIn("复现", text)
        self.assertNotIn("复现与借鉴价值", text)
        self.assertIn("baseline 是否公平", text)
        self.assertIn("实验设置", text)
        self.assertIn("主对比基线", text)

    def test_concept_reference_defines_seed_vocabulary_and_three_way_paper_method_policy(self):
        text = CONCEPT_CATEGORIES.read_text(encoding="utf-8")

        self.assertIn("## Systems Concept Seed Vocabulary", text)
        for concept_type in [
            "data-structure",
            "algorithm",
            "mechanism",
            "architecture",
            "hardware",
            "software-abstraction",
            "metric",
            "theory-model",
        ]:
            self.assertRegex(text, rf"(?m)^\|\s*{re.escape(concept_type)}\s*\|")

        for seed in ["RDMA", "NVLink", "PCIe", "NUMA", "HBM", "CXL", "AllReduce", "NCCL", "CUDA"]:
            self.assertIn(seed, text)

        self.assertIn("论文首创 + 仅本论文实验", text)
        self.assertIn("论文具名实现 + 前人工作 / 被多篇当 baseline", text)
        self.assertIn("完全是前人工作 + 该论文只是引用", text)

    def test_concept_generation_prompts_prefer_recall_and_exclude_datasets(self):
        paper_reader = PAPER_READER_SKILL.read_text(encoding="utf-8")
        concept_skill = CONCEPT_NOTES_SKILL.read_text(encoding="utf-8")
        combined = "\n".join([paper_reader, concept_skill])

        self.assertIn("宁可漏判几个通用词，也不要误杀真正的 systems concept", combined)
        self.assertIn("不确定就创建", combined)
        self.assertIn("数据集 / 仿真器不作为 concept", combined)
        self.assertIn("seed list", combined)
        self.assertIn("首次出现必须写成 `[[概念名]]`", combined)
        self.assertIn("Admission Control", combined)
        self.assertIn("Kernel Fusion", combined)

    def test_concept_reference_uses_enhanced_template_with_required_sections(self):
        text = CONCEPT_CATEGORIES.read_text(encoding="utf-8")
        template = CONCEPT_TEMPLATE.read_text(encoding="utf-8")

        # 8 个统一段按顺序写在 assets 模板里，reference 指向模板
        sections = ["## 定义", "## 动机与痛点", "## 直观例子", "## 核心要点",
                    "## 边界与对比", "## 代表工作与具体用法", "## 相关概念", "## 学习索引"]
        positions = [heading_index(template, s) for s in sections]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("assets/concept-note-template.md", text)
        self.assertIn("TODO: 待人工补充学习材料", template)

        # 长度按直观例子和其他段分别计，并给出自检脚本
        self.assertIn(CONCEPT_LENGTH_RULE, text)
        self.assertIn("check_concept_length.py", text)
        self.assertNotIn("60-100 行", text)

        # 学习索引允许整段写 TODO 的硬规则
        self.assertIn("TODO: 待人工补充学习材料", text)

    def test_zotero_writes_go_through_the_local_api(self):
        skill = PAPER_READER_SKILL.read_text(encoding="utf-8")
        guide = (REPO_ROOT / "skills" / "paper-reader" / "references" / "zotero-guide.md").read_text(encoding="utf-8")
        for command in ["set-field", "trash"]:
            self.assertIn(command, skill)
            self.assertIn(f"zotero_helper.py {command}", guide)
        for blob in (skill, guide):
            self.assertIn("本地 API", blob)
            self.assertIn("--apply", blob)
        self.assertNotIn("会修改 Zotero 数据库", guide)

    def test_note_title_carries_the_venue_label(self):
        template = ASSET_TEMPLATE.read_text(encoding="utf-8")
        skill = PAPER_READER_SKILL.read_text(encoding="utf-8")

        self.assertIn("# 论文笔记：{Title} ({VenueLabel})", template)
        self.assertIn("venue: {VenueShort}", template)
        self.assertIn("venue_label", skill, "paper-reader SKILL.md 没有说明标题标签")
        self.assertIn("venue_label.py", skill)

    def test_concept_reference_lists_per_type_differentiation_sections(self):
        text = CONCEPT_CATEGORIES.read_text(encoding="utf-8")

        # 8 类各自的差异化段都要在 reference 里列出
        differentiation_sections = [
            "## 内存视图 / 字段布局",           # data-structure
            "## 步骤",                          # algorithm
            "## 复杂度",                        # algorithm
            "## 状态与触发条件",                # mechanism
            "## 关键参数",                      # mechanism
            "## 组件与接口",                    # architecture
            "## 接口与典型参数",                # hardware
            "## API 与生命周期",                # software-abstraction
            "## 测量方法",                      # metric
            "## 假设与失效边界",                # theory-model
        ]
        for section in differentiation_sections:
            self.assertIn(section, text)

        # architecture 类必须用 Mermaid,不允许 ASCII 替代
        self.assertIn("不允许 ASCII", text)
        self.assertIn("Mermaid", text)

    def test_concept_rules_live_in_concept_skill_and_readers_delegate(self):
        paper_reader = PAPER_READER_SKILL.read_text(encoding="utf-8")
        concept_skill = CONCEPT_NOTES_SKILL.read_text(encoding="utf-8")
        regenerate = REGENERATE_CONCEPTS.read_text(encoding="utf-8")

        # 增强模板的 4 个必选段、长度规则、长度自检只写在 concept-notes
        for keyword in ["动机与痛点", "直观例子", "边界与对比", "学习索引"]:
            self.assertIn(keyword, concept_skill, f"concept-notes SKILL.md 缺少关键词 {keyword}")
        for blob, name in [(concept_skill, "concept-notes SKILL.md"), (regenerate, "regenerate_concepts.py")]:
            self.assertIn(CONCEPT_LENGTH_RULE, blob, f"{name} 缺少长度规则")
        self.assertIn("check_concept_length.py", concept_skill)
        for blob in (paper_reader, concept_skill, regenerate):
            self.assertNotIn("60-100 行", blob)

        # paper-reader 交给 concept-notes 模式 E，不再自己抄一份规则
        self.assertIn("模式 E", paper_reader, "paper-reader SKILL.md 没有调用 concept-notes 模式 E")
        self.assertNotIn(CONCEPT_LENGTH_RULE, paper_reader, "paper-reader SKILL.md 又复制了一份概念长度规则")
        self.assertNotIn("宁可漏判几个通用词", paper_reader, "paper-reader SKILL.md 又复制了一份概念过滤规则")

    def test_paper_reader_zotero_workflow_is_readonly_and_collection_path_based(self):
        text = PAPER_READER_SKILL.read_text(encoding="utf-8")
        asset_text = ASSET_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("zotero_item_id: {zotero_item_id}", asset_text)
        self.assertIn("zotero_collection: {zotero_path}", asset_text)
        self.assertIn("Zotero 默认只读", text)
        self.assertIn("{NOTES_PATH}/{selected_collection_path}/{MethodName}.md", text)
        self.assertIn("批量从 collection 进入时", text)
        self.assertIn("确认后才调用", text)

    def test_figure_and_formula_guidance_asks_for_natural_explanations(self):
        template_text = ASSET_TEMPLATE.read_text(encoding="utf-8")
        standards_text = QUALITY_STANDARDS.read_text(encoding="utf-8")

        combined_text = "\n".join([template_text, standards_text])
        natural_guidance = [
            "自然段",
            "论证链",
            "关键趋势",
            "支撑的设计或结论",
        ]
        for phrase in natural_guidance:
            self.assertIn(phrase, combined_text)

    def test_image_titles_live_in_image_captions_not_separate_lines(self):
        template_text = ASSET_TEMPLATE.read_text(encoding="utf-8")
        paper_reader = PAPER_READER_SKILL.read_text(encoding="utf-8")
        standards_text = QUALITY_STANDARDS.read_text(encoding="utf-8")
        combined_text = "\n".join([template_text, paper_reader, standards_text])

        self.assertNotIn("加粗图注行", combined_text)
        self.assertNotIn("`**Figure X:", combined_text)
        self.assertNotIn("`**Figure 3:", combined_text)

        image_refs = re.findall(r"!\[([^\]]*)\]\([^)]*\)", template_text)
        self.assertTrue(image_refs)
        self.assertTrue(all(caption.startswith("Figure ") for caption in image_refs))

    def test_local_pdf_image_guidance_uses_00_assets_and_note_name_prefix(self):
        paper_reader = PAPER_READER_SKILL.read_text(encoding="utf-8")
        standards = QUALITY_STANDARDS.read_text(encoding="utf-8")
        combined = "\n".join([paper_reader, standards])

        for phrase in [
            "00_assets",
            "<note-name>_<原图片名>",
            "note-name ≤ 48 字符",
            "截断前 40 字符 + 8 位 hash",
        ]:
            self.assertIn(phrase, combined)

        self.assertIn("![[00_assets/", combined)
        self.assertNotRegex(combined, r"!\[\[00_assets/[^]]*\|600\]\]")

    def test_diagram_rules_define_selection_table_and_fallback(self):
        text = DIAGRAM_RULES.read_text(encoding="utf-8")

        assert_table_header(self, text, ["图的类型", "默认工具", "备注"])
        for phrase in [
            "drawio --version", "DRAWIO_SKILL_DIR", "VERILOG_DIAGRAM_DIR",
            "seqlayout.py", "arch2drawio.py", "validate.py", "repair_png.py",
            "退回 Mermaid", ".drawio.png", "00_assets/", "^diag-",
            "references/mermaid-rules.md",
        ]:
            self.assertIn(phrase, text, phrase)
        self.assertIn("-f xml", text)          # .mmd 先转 .drawio，再导出
        self.assertNotIn("-f svg", text)       # 不走 SVG

    def test_template_section_order_follows_problem_evidence_design_chain(self):
        text = ASSET_TEMPLATE.read_text(encoding="utf-8")
        idx = lambda heading: heading_index(text, heading)
        self.assertLess(idx("## 这篇论文为什么重要"), idx("## 问题定义"))
        self.assertLess(idx("## 问题定义"), idx("## 动机实验与核心 Insights"))
        # 核心贡献回应 Insight 指出的问题，再引出设计：问题 → 证据 → 贡献 → 设计
        self.assertLess(idx("## 动机实验与核心 Insights"), idx("## 核心贡献"))
        self.assertLess(idx("## 核心贡献"), idx("## 系统设计总览"))
        self.assertLess(idx("## 系统设计总览"), idx("## 关键机制拆解"))
        self.assertLess(idx("## Overhead 与兼容性"), idx("### 实现改动清单"))
        self.assertLess(idx("### 实现改动清单"), idx("### Overhead"))
        overview = text[idx("## 系统设计总览"):idx("## 关键机制拆解")]
        self.assertNotIn("### 实现改动清单", overview)

    def test_template_summary_and_problem_sections_carry_no_evidence(self):
        text = ASSET_TEMPLATE.read_text(encoding="utf-8")
        summary = text[heading_index(text, "## 这篇论文为什么重要"):heading_index(text, "## 问题定义")]
        problem = text[heading_index(text, "## 问题定义"):heading_index(text, "## 动机实验与核心 Insights")]
        for marker in ("![", "$$", "|---"):
            self.assertNotIn(marker, summary, marker)
        for marker in ("![", "|---"):
            self.assertNotIn(marker, problem, marker)

    def test_template_system_architecture_offers_original_figure_or_self_drawn(self):
        text = ASSET_TEMPLATE.read_text(encoding="utf-8")
        arch = text[heading_index(text, "### 系统架构"):heading_index(text, "### 执行流")]
        flow = text[heading_index(text, "### 执行流"):heading_index(text, "### 优化目标与度量口径")]
        self.assertEqual(arch.count("![Figure"), 1)
        self.assertEqual(arch.count("![[00_assets/<note-name>_arch.png|"), 1)
        self.assertIn("二选一", arch)
        self.assertIn("diagram-rules.md", arch)
        self.assertNotIn("```mermaid", flow)
        self.assertRegex(flow, r"(?m)^1\. ")
        self.assertIn("[[#机制1：", flow)

    def test_template_anchor_examples(self):
        text = ASSET_TEMPLATE.read_text(encoding="utf-8")
        self.assertGreaterEqual(len(re.findall(r"\) \^fig\d+\s*$", text, re.M)), 2)
        self.assertIn("\n\n^tab-components\n\n", text)
        self.assertRegex(text, r"(?m)^\d\. .+ \^contrib-\d$")
        for link in ("[[#^fig1|Figure 1]]", "[[#^contrib-1|贡献1]]", "[[#^tab-components|组件表]]"):
            self.assertIn(link, text, link)
        for heading, short in (("机制1", "机制1"), ("Insight 1", "Insight 1")):
            m = re.search(rf"(?m)^### {re.escape(heading)}：(.+)$", text)
            self.assertIsNotNone(m, heading)
            self.assertIn(f"[[#{heading}：{m.group(1)}|{short}]]", text)
        self.assertIn("## 笔记内跳转", QUALITY_STANDARDS.read_text(encoding="utf-8"))

    def test_skill_names_current_template_structure(self):
        skill = PAPER_READER_SKILL.read_text(encoding="utf-8")
        for name, blob in (("SKILL.md", skill),):
            for fresh in ["动机实验与核心 Insights", "### 系统架构", "执行流", "实现改动清单",
                          "diagram-rules.md", "论文原图", "[[#^"]:
                self.assertIn(fresh, blob, f"{name} lacks {fresh}")
        self.assertIn("`_shared/references/diagram-rules.md`", skill)
        self.assertIn("退回 Mermaid", skill)

    def test_template_fig_placeholders_are_not_valid_block_ids(self):
        text = ASSET_TEMPLATE.read_text(encoding="utf-8")
        # 图片行上的锚点要么是具体编号（^fig1），要么是一眼可见的占位符（^fig{X}），不能是像 id 的 ^figX
        for anchor in re.findall(r"\) \^fig(\S+)", text):
            self.assertRegex(anchor, r"^(?:\d+|\{X\})$", anchor)
        self.assertIn(") ^fig{X}", text)
        self.assertNotIn(" ^figX", text)

    def test_formula_location_rule_names_design_space_section(self):
        template_lines = ASSET_TEMPLATE.read_text(encoding="utf-8").splitlines()
        rule_2 = next(line for line in template_lines if line.startswith("2. 公式和图表必须嵌入"))
        self.assertIn("现有方法与设计空间", rule_2)

    def test_diag_anchor_placement_consistent_across_rule_files(self):
        for path in (QUALITY_STANDARDS, DIAGRAM_RULES):
            text = path.read_text(encoding="utf-8")
            self.assertIn("嵌入行在行尾", text, path.name)
            self.assertIn("代码块之后单独一行", text, path.name)

    def test_skill_requires_reporting_diagram_route(self):
        self.assertIn("哪条路线", PAPER_READER_SKILL.read_text(encoding="utf-8"))

    def test_section_order_statements_place_contributions_after_insights(self):
        order = "`问题定义` → `动机实验与核心 Insights` → `核心贡献` → `系统设计总览`"
        self.assertEqual(PAPER_READER_SKILL.read_text(encoding="utf-8").count(order), 2)
        rule_9 = next(line for line in ASSET_TEMPLATE.read_text(encoding="utf-8").splitlines()
                      if line.startswith("9. "))
        self.assertIn("核心贡献", rule_9)

    def test_execution_flow_diagram_is_conditional_and_not_a_second_architecture_view(self):
        text = ASSET_TEMPLATE.read_text(encoding="utf-8")
        flow = text[heading_index(text, "### 执行流"):heading_index(text, "### 优化目标与度量口径")]
        # 条件写在占位说明里，模板不放默认图块，避免每篇都照抄一张
        self.assertNotIn("```mermaid", flow)
        for trigger in ("5 步", "反馈", "并行", "带方向的箭头"):
            self.assertIn(trigger, flow, trigger)
        for phrase in ("^diag-flow", "diagram-rules.md", "编号", "不要重画"):
            self.assertIn(phrase, flow, phrase)
        skill = PAPER_READER_SKILL.read_text(encoding="utf-8")
        for name, blob in (("template", text), ("SKILL.md", skill)):
            self.assertNotIn("不画第二张框图", blob, name)
            self.assertIn("^diag-flow", blob, name)
            # 触发条件要能直接观察：步数按列表条数，普通请求-响应不算闭环，第 4 条看架构图有没有顺序箭头
            for phrase in ("按编号列表条数计", "单纯的请求-响应返回不算", "回到上游模块或自身", "没有带方向的箭头或步骤编号"):
                self.assertIn(phrase, blob, (name, phrase))
            self.assertNotIn("架构图看不出执行顺序", blob, name)
        self.assertIn("^diag-flow", QUALITY_STANDARDS.read_text(encoding="utf-8"))

    def test_critical_thinking_merges_limits_with_failure_scenarios(self):
        text = ASSET_TEMPLATE.read_text(encoding="utf-8")
        critical = text[heading_index(text, "## 批判性思考"):heading_index(text, "## 经验与可迁移启示")]
        self.assertEqual(
            re.findall(r"(?m)^### (.+)$", critical),
            ["优点", "局限、假设与失效场景", "潜在改进方向"],
        )
        self.assertIn("**失效场景**", critical)

    def test_skill_requires_post_write_link_check(self):
        skill = PAPER_READER_SKILL.read_text(encoding="utf-8")
        self.assertIn("python3 scripts/check_note_links.py", skill)
        # 复查范围包括本次新建的概念笔记，根目录说清是 VAULT_PATH
        for phrase in ("新建的概念笔记", "VAULT_PATH"):
            self.assertIn(phrase, skill, phrase)
        template_rule_13 = next(line for line in ASSET_TEMPLATE.read_text(encoding="utf-8").splitlines() if line.startswith("13. "))
        self.assertIn("新建的概念笔记", template_rule_13)
        # 复查放在补概念之后：概念笔记建好后，[[概念]] 链接才可能全部解析
        self.assertLess(skill.index("## 5. 附带生成本篇新概念"), skill.index("python3 scripts/check_note_links.py"))

    def test_diagram_rules_gate_verilog_only_for_pipeline_route(self):
        text = DIAGRAM_RULES.read_text(encoding="utf-8")
        self.assertIn("仅该路线退回", text)
        self.assertNotIn('[ -d "$DRAWIO" ] && [ -d "$VLOG" ]', text)
        self.assertNotIn("同目录的 `references/", text)
        self.assertIn("_shared/references/mermaid-rules.md", text)


if __name__ == "__main__":
    unittest.main()
