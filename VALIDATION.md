# 公开版验证记录

日期：2026-10-18；CPython 3.14.7，标准库计算。完整机器可读结果见 [validation-results.json](validation-results.json)。

## 本轮实际执行

- Skill创建工具的格式验证通过。
- 13项行为测试通过，包括独立峰值、正反向与零位移、约束与边界、输入拒绝和输出保护。
- 默认轨迹在隔离目录重新计算；独立系数与导数根核查在已保存结果和新运行结果上分别通过201/201项。两次核查使用同一个验证器，不能当作402个独立测试设计。
- 24份CSV和2份SVG与保存结果散列一致；原清单的全部输出和两份脚本散列吻合。
- 读图配图生成器实际重跑，2份SVG、数据CSV和检查JSON共4份输出散列一致；4行数据的每行6个字段与原summary一致。
- 两份PNG的散列与尺寸符合保存记录，使用2026-10-17已完成的实际视觉审阅；本轮没有重新执行浏览器PNG导出。
- 核查本地Markdown链接、已知源文件／媒体散列、排除的内部索引及常见凭据／用户绝对路径模式。

## 复现

在仓库根目录执行；输出选新目录：

```text
python -m unittest discover -s tests -v
python skills/research-workflow/scripts/trajectory_benchmark.py --input skills/research-workflow/assets/trajectory-input.json --output rerun/default
python skills/research-workflow/scripts/verify_trajectory.py --input skills/research-workflow/assets/trajectory-input.json --output rerun/default
python examples/figure-reading-and-design/make_figures.py --summary examples/trajectory-planning/summary.json --output rerun/figures
python tools/check_release.py --public
```

发布检查依据 [PUBLIC_RELEASE_REVIEW.md](PUBLIC_RELEASE_REVIEW.md)的原创包范围，不表示原指南授权状态发生变化。发布门槛在检查未完成时实际返回2；完成内容审阅和验证后应返回0。

## 限制

201项是浮点数值核查而非形式化证明；结论只限单轴固定五次／七次形状族。没有硬件、闭环振动、多轴耦合或全局时间最优性验证。图形不是独立的新实验，PNG跨平台字节一致性不作保证。文件散列和模式扫描不能代替人工内容审阅或证明全部第三方权利。
