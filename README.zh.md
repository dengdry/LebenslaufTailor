# Resume Tailor Local

[English](README.md) | [Deutsch](README.de.md) | [中文](README.zh.md)

Resume Tailor Local 是一个注重隐私的本地简历定制工具。它可以读取简历，根据粘贴的岗位 JD 进行匹配评分，可选调用 LLM 改写内容，并导出定制后的 HTML 简历和 PDF。

当前项目重点是德国 / 欧洲风格简历，也支持根据 JD 语言在德语和英语之间切换输出。

## 功能

- 读取 `.docx` 简历，包括普通段落和 Word 文本框内容。
- 读取本工具生成的 HTML 简历，并作为后续修改的 Master Resume。
- 粘贴 JD 后生成匹配度分析报告。
- 支持规则评分和可选 LLM 语义评分。
- 支持 OpenAI、DeepSeek、Ollama，也可以关闭 LLM，只使用本地规则模式。
- 根据 JD 改写个人简介、技能和工作经历要点。
- 对 LLM 输出做基础事实保护，避免无依据添加项目、客户、证书、职位等内容。
- 根据 JD 语言生成德语或英语简历。
- 输出 HTML/CSS，并通过本机 Microsoft Edge 或 Google Chrome 导出 PDF。
- 在图形界面中查看修改对照、手动编辑、预览 HTML 和导出 PDF。
- 自动缓存 LLM 返回结果，减少重复测试时的 token 消耗。

## 运行要求

- Windows 10/11
- Python 3.11 或更高版本
- Microsoft Edge 或 Google Chrome，用于 HTML 转 PDF
- 可选：OpenAI / DeepSeek API Key，或本地 Ollama

安装依赖：

```bash
python -m pip install -r requirements.txt
```

启动图形界面：

```bash
python gui.py
```

Windows 下也可以双击：

```bat
start_gui.bat
```

`start_gui.bat` 会自动创建本地 `.venv` 并安装依赖。`.venv/` 已加入 `.gitignore`。

## 快速开始

1. 在桌面软件里点击 `填写/编辑简历`。
2. 在编辑窗口里把 Max Mustermann 的虚构内容改成自己的，并保存为 `master_resume.html`。
3. 在 JD 文本框中粘贴岗位描述。
4. 选择模型服务：`off`、`openai`、`deepseek` 或 `ollama`。
5. 点击 `1. Analyze` 生成匹配评分。
6. 点击 `2. Generate Resume` 生成定制版 HTML 简历。
7. 点击 `3. Review & Edit` 检查并手动调整结果。
8. 点击 `4. Preview` 打开生成后的 HTML。
9. 点击 `5. Export PDF` 生成最终投递文件。

当前 GUI 仍然包含中文标签，因为项目最初来自一个本地个人工作流。后续可以继续做国际化。

## 没有简历时如何开始

已经填好内容的示例模板是：

```text
resume_templates/mustermann_resume_template.html
```

用户不需要手动编辑 HTML 源码。打开软件后点击 `填写/编辑简历`，程序会用类似表单的界面读取这个模板并保存成自己的 Master Resume。

## HTML 作为 Master Resume

推荐工作流：

```text
填写好的 HTML 简历 -> 新 JD -> 定制版 HTML/PDF
```

GUI 现在刻意采用 HTML-first 流程。DOCX 解析能力仍保留在命令行里，但桌面端主流程围绕可编辑 HTML 模板设计。

## LLM 设置

在 GUI 中输入 API Key 并保存后，配置会写入：

```text
.config/settings.json
```

`.config/` 已加入 `.gitignore`。

也可以通过环境变量配置：

```bash
RESUME_TAILOR_LLM=deepseek
RESUME_TAILOR_MODEL=deepseek-v4-flash
DEEPSEEK_API_KEY=your_api_key
```

```bash
RESUME_TAILOR_LLM=openai
RESUME_TAILOR_MODEL=gpt-5.2
OPENAI_API_KEY=your_api_key
```

```bash
RESUME_TAILOR_LLM=ollama
RESUME_TAILOR_MODEL=llama3.1
OLLAMA_BASE_URL=http://localhost:11434
```

## LLM 缓存

程序会缓存 LLM 返回结果，减少重复测试成本。

- 缓存目录：`.cache/llm/`
- 缓存条件：模型服务、模型名、系统提示词、用户提示词完全一致
- 删除 `.cache/llm/` 可以强制重新调用模型

`.cache/` 已加入 `.gitignore`。

## 命令行示例

```bash
python app.py analyze --resume "path/to/resume.docx" --jd jd.txt --out outputs/match_report.md
python app.py analyze --html outputs/tailored_lebenslauf.html --jd jd.txt --out outputs/match_report.md
python app.py tailor-html --resume "path/to/resume.docx" --jd jd.txt --template "path/to/template.docx" --out outputs/tailored_lebenslauf.html
python app.py export-pdf --html outputs/tailored_lebenslauf.html --out outputs/tailored_lebenslauf.pdf
```

## 项目结构

```text
.
├── app.py                         # 命令行入口
├── gui.py                         # Tkinter 图形界面
├── resume_tailor/
│   ├── export/                    # HTML/PDF/DOCX 导出
│   ├── llm/                       # OpenAI / DeepSeek / Ollama 客户端
│   ├── parsing/                   # DOCX / HTML 解析
│   ├── rewriting/                 # 规则和 LLM 改写
│   ├── scoring/                   # 匹配评分
│   └── writers/                   # 报告输出
├── templates/                     # 程序渲染模板
├── resume_templates/              # 可直接预览的完整示例模板
├── examples/                      # 匿名示例简历和示例 JD
├── requirements.txt
└── start_gui.bat
```

## 隐私说明

这是一个本地工具。简历、JD 和生成文件默认保存在本机。

如果启用 OpenAI 或 DeepSeek，程序会把 JD 和结构化简历内容发送给所选 API 服务商。如果非常介意隐私，可以使用 `off` 模式、本地 Ollama、匿名测试数据，并定期清理 `.config/`、`.cache/` 和 `outputs/`。

## 开源协议

MIT License。详见 [LICENSE](LICENSE)。
