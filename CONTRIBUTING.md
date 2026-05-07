# Contributing

欢迎贡献。这个项目目前更像一个正在产品化的本地工具，所以最有价值的贡献通常是：

- 改进不同简历模板的解析稳定性；
- 改进 HTML/CSS 简历模板；
- 补充英文 / 德文 JD 的改写质量；
- 增加测试样例，但不要提交真实简历或真实 API Key；
- 修复 PDF 导出、分页和布局问题。

## 本地开发

```bash
python -m pip install -r requirements.txt
python gui.py
```

提交前建议运行：

```bash
python -m compileall app.py gui.py resume_tailor
python app.py --help
```

## 隐私

不要提交以下内容：

- 真实简历；
- 真实 JD；
- API Key；
- `.config/`；
- `.cache/`；
- `outputs/`。

这些路径已经写入 `.gitignore`。
