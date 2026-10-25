---
type: concept
aliases: [{中文别名}, {英文别名}]
concept_type: {concept_type}  # 从 references/concept-categories.md 的 8 类选一
tags: [status/paper-specific]  # 仅在 paper-specific 时加，否则删掉这一行
---

<!--
写作约束（规则全文见 ../references/concept-categories.md）：
1. 8 个统一段 + 1 个按 concept_type 加的差异化段；差异化段放在 `## 核心要点` 之后、`## 边界与对比` 之前，段名按 concept-categories.md 的“按 concept_type 差异化段”表。
2. 长度：直观例子 ≤ 100 行、其他段 ≤ 90 行（不计 frontmatter 和图的源码）。写完运行 `python3 ~/.claude/skills/concept-notes/scripts/check_concept_length.py <概念笔记>` 自检。
3. `## 直观例子` 按 concept-categories.md 的“直观例子写作规则”写成分步推导 + 配图 + 数值算例。
4. 自画图按 skill 目录下的 `_shared/references/diagram-rules.md`：默认 diagram-design 导出 PNG 到 `00_assets/<note-name>_<desc>.png` 嵌入，空间结构用 matplotlib，不可用时才退回 Mermaid；不允许 ASCII 状态图。
5. 动机、直观例子只能从论文证据推断，禁止凭空编造；找不到证据写 `TODO`。
-->

# {概念名称}

## 定义
{一句话定义。只解释 what，不解释 why。}

## 动机与痛点
{为什么会出现这个 concept？它在解决什么瓶颈或抽象漏洞？跟它之前人们怎么做相比，核心改进是什么？}

## 直观例子
{用 1 个具体场景把 concept “走一遍”：先交代场景和假设，再用 `### 第 N 步：<这一步回答的问题>` 逐步推出结论，每个数字都给出来源；至少配 1 张图（diagram-design 或 matplotlib 导出的 PNG），并做一个代入具体数值的算例。目标：读者不用自己补中间步骤，读完就能复述“它为什么是这个结果”。}

## 核心要点
{3-5 条，每条用一两句解释**原理**，不只是 fact 列表。}

<!-- 差异化段：data-structure → ## 内存视图 / 字段布局；algorithm → ## 步骤 + ## 复杂度；mechanism → ## 状态与触发条件 + ## 关键参数；architecture → ## 组件与接口（必须有组件图）；hardware → ## 接口与典型参数；software-abstraction → ## API 与生命周期；metric → ## 测量方法；theory-model → ## 假设与失效边界 -->

## {差异化段名}
{按 concept_type 写。}

## 边界与对比
- {什么情况**不**适用 / 反模式}
- {跟最容易混淆的近邻 concept 的关键差别（用 1-2 个 `[[xxx]]` 对比）}

## 代表工作与具体用法
- [[{Paper1}]]: {它怎么使用这个 concept？用出了什么效果（具体数字 / 设计决策）？}
- [[{Paper2}]]: {同上}

## 相关概念
- [[{concept1}]]: {和本概念的**关系**（组成 / 替代 / 协作 / 前置）}
- [[{concept2}]]: {同上}

## 学习索引
- {入门 paper / 综述：1-2 个（必须有具体 URL 或论文标题，不要凭印象列）}
- {经典 blog / 教科书章节：1-2 个（必须有 URL）}
- {关键 GitHub 实现（可选）}

> 学习索引段允许整段写 `TODO: 待人工补充学习材料`，不要硬凑虚构内容。
