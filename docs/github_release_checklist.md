# GitHub 发布检查清单

发布前建议检查：

- [ ] `README.md` 中没有本机绝对路径。
- [ ] `app.py`、`gui.py` 中没有真实姓名、邮箱、电话、地址。
- [ ] `.config/` 没有被提交。
- [ ] `.cache/` 没有被提交。
- [ ] `outputs/` 没有被提交。
- [ ] 没有真实简历、真实 JD 或 API Key。
- [ ] 本地运行 `python -m compileall app.py gui.py resume_tailor`。
- [ ] 本地运行 `python app.py --help`。
- [ ] GitHub 仓库描述里说明：本地简历定制工具，支持 HTML/PDF 输出和可选 LLM。
