---
name: "paper-to-zotero"
description: "Use when the user gives a paper title, DOI, arXiv ID or link and wants it downloaded or 入库 into Zotero (加到/下载到 Zotero、放进某个分类、找 PDF 放进 Zotero)."
---

# 论文入库 Zotero（paper-to-zotero）

把一篇论文从“题目 / DOI / 链接”变成 Zotero 里一条带 PDF、放在正确分类下的条目。所有写入都走 Zotero 10 的本地 API（`http://localhost:23119/api`），不碰 `zotero.sqlite`，Zotero 界面立刻看到，照常同步。

**铁律**：没拿到 PDF 就不建条目，停下来等用户；入库成功后只问一次要不要精读，不自动开始精读。

## 前提

- Zotero 10 已打开，设置 → 高级 里启用了本地 API。
- 第一次写入 Zotero 会弹授权框，请用户点 **Always Allow**；只点 Allow 的话一篇论文要弹 4 次（建条目、建附件、上传授权、登记上传），每分钟最多 5 次。
- 下面的命令都在本 skill 目录下运行，脚本是 `scripts/zotero_add.py`（只用 Python 标准库）。

## 流程

### 1. 识别输入，拿到元数据

| 输入 | 元数据来源 |
|------|-----------|
| DOI 或含 DOI 的链接 | `curl -sL -H "Accept: application/vnd.citationstyles.csl+json" https://doi.org/<DOI>` |
| arXiv 链接 / ID | `curl -s "http://export.arxiv.org/api/query?id_list=<ID>"`（Atom，含标题、作者、摘要、DOI） |
| 只有题目 | 先搜 arXiv `search_query=ti:"<题目>"`，再搜 `https://api.crossref.org/works?query.title=<题目>&rows=3`；多个候选时列出让用户选 |
| 出版社页面链接 | WebFetch 页面拿 DOI，再按 DOI 走 |

写成 `meta.json`（Zotero Web API 字段名，`creators` 用 `firstName`/`lastName`）：

```json
{"itemType": "conferencePaper",
 "title": "...", "creators": [{"creatorType": "author", "firstName": "Ada", "lastName": "Lovelace"}],
 "date": "2025-06", "DOI": "10.1109/...", "url": "https://...",
 "proceedingsTitle": "Proceedings of the 52nd Annual International Symposium on Computer Architecture (ISCA '25)",
 "abstractNote": "..."}
```

- 期刊用 `journalArticle` + `publicationTitle`/`volume`/`issue`/`pages`；会议用 `conferencePaper` + `proceedingsTitle`；arXiv 预印本用 `preprint` + `repository: "arXiv"` + `archiveID: "arXiv:2501.01234"`。
- 会议名写全称并带年份缩写，和库里现有条目一致，别写成 "ISCA" 一个词。
- 摘要必须填：第 3 步分类和之后 paper-reader 都靠它。

### 2. 查重

```bash
python3 scripts/zotero_add.py search "<题目前几个词>"
```

每个命中会列出条目链接、所在的全部 collection（完整路径）和本地 PDF 路径：导入到 Zotero 存储的读 `links.enclosure`，ZotMoov 这类链接附件（`attachments:…`）拼上 Zotero 的“链接附件根目录”（`$ZOTERO_BASE_ATTACHMENT_PATH`，没设时读 Zotero 的 `prefs.js`）；文件不在时标 `(file missing)`。

命中同一篇就停，不要再建一条。把这些原样告诉用户：

- 条目已存在：`zotero://select/library/items/<KEY>`
- 所在 collections：每条完整路径一行
- 本地 PDF：路径；没有 PDF 或标了 `(file missing)` 时直说

然后问是否只补 PDF 或调整分类。

### 3. 判定放进哪个叶子分类

```bash
python3 scripts/zotero_add.py collections        # 打印分类根下的树，叶子带 key 和说明
```

分类根和每个叶子的说明来自配置的 `paper_to_zotero` 段（见 README「配置」）。默认配置 `../_shared/user-config.json` 带一套体系结构分类作参考：根是 `Computer Architecture`，下面 18 个叶子各有一句说明。用户想按自己的方式分类时，在个人配置 `~/.config/arch-reading-skills/user-config.json` 里改：

```json
"paper_to_zotero": {
  "collection_root": "My Papers",
  "collection_hints": {
    "Systems / Storage": "SSD、文件系统、I/O 路径"
  }
}
```

- `collection_root` 为空时列出整个库的所有顶层分类。
- **库里没有 `collection_root` 这个分类时，脚本报错退出，这时整个流程停在这里，不下载、不建条目。** 把脚本输出转告用户：原因（库里没有这个分类，以及现有的顶层分类有哪些）和三种处理办法（在 Zotero 里建这个分类；在个人配置里把 `collection_root` 改成自己的分类根，可顺带写 `collection_hints`；设成 `""` 在整个库里挑）。等用户改好再从第 3 步重来；不要替用户改配置，也不要自己换一个分类根。
- `collection_hints` 的键是叶子相对分类根的路径（` / ` 分隔），值写这个叶子放什么。说明只印在库里真实存在的叶子旁边，对不上的默认说明自动不显示；没有说明的叶子只按名字和所在路径判断。

只放**叶子**分类，父级分类本身通常是空的，用户靠叶子组织。读摘要和引言，按**主要贡献所在的层**判：

- 两个都像时取主贡献那一层：例如提出硬件机制归机制所在分类，只做测量归“刻画 / 测量”类，只做平台归“评测平台”类。
- 都不像时不要硬塞：列出最接近的两个让用户选，或建议放一个待分类的集合（如 `_Review/Needs Classification`，库里有的话）。
- 论文若明显也属于分类根之外的某个集合（如按研究课题组织的集合），在汇报里顺带提一句“也可加进 …”，用户点头后再加第二个 `--collection`，不要自己加。
- 用户第一次用、库里分类结构和说明都很少时，可以建议用户把常用叶子的说明写进 `collection_hints`，但不要替用户改配置文件。

### 4. 下载 PDF

按顺序试，拿到第一个真 PDF 就停；文件名 `<第一作者姓>_<年>_<标题前三四个词>.pdf`，放 `~/Downloads/paper-to-zotero/`：

1. arXiv：`https://arxiv.org/pdf/<ID>`（有 arXiv ID 或题目在 arXiv 搜得到）。
2. 开放获取：`curl -s "https://api.openalex.org/works/https://doi.org/<DOI>"` 取 `best_oa_location.pdf_url`；再试 `https://api.semanticscholar.org/graph/v1/paper/DOI:<DOI>?fields=openAccessPdf`。
3. 出版社直链（校园网 / VPN 下有效）：IEEE `https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber=<编号>`（编号在 DOI 末尾或页面里）；ACM `https://dl.acm.org/doi/pdf/<DOI>`；USENIX 页面上的 pdf 链接。

每次下载后验证：`head -c 5 文件` 必须是 `%PDF-`，且大小大于 50 KB；否则是登录页或 HTML，删掉继续下一个来源。

**全部失败 → 在这里停下，不建条目。** 汇报三件事：元数据（题目、venue、年）、判定的分类和理由、试过的来源。然后等用户：用户给一个本地 PDF 路径就接着第 5 步；用户说“不要 PDF 先建条目”就不带 `--pdf` 执行第 5 步。

### 5. 入库

```bash
python3 scripts/zotero_add.py add --meta meta.json --pdf "<pdf 路径>" --collection <叶子 key>
```

成功输出 `item created: <KEY>` 和 `pdf attached`。汇报：题目、分类路径、`zotero://select/library/items/<KEY>`。脚本在中途失败会说明哪一步失败、哪些已建好，不要重跑整条命令造成重复条目；按提示补做或让用户在 Zotero 里处理。

### 6. 问一次是否精读

入库成功后问一句：“要不要用 paper-reader 精读这篇？”用户同意就调用本仓库的 `paper-reader` skill（带 Zotero 集成），入口写成“读一下 Zotero 里的 <题目>”，它会按 Zotero 分类路径把笔记存到 `PaperNotes/<分类路径>/`。用户没回或说不用，就到此结束。

## 常见错误

- 分类根不存在时自己换个分类继续 → 应该停下，把原因和配置方法告诉用户。

- 把条目放进父级分类 → 只能放叶子。
- 把没有 PDF 的条目先建上 → 违反铁律，用户要的是“拿不到就停”。
- 下载到的是 HTML 登录页当成 PDF 传上去 → 验证 `%PDF-` 头和大小。
- 不查重直接建 → 库里出现重复条目。
- 摘要没填 → 分类判断没有依据，paper-reader 也少了信息。
- 用户还没说“精读”就开始跑 paper-reader → 只问一次，等回答。
