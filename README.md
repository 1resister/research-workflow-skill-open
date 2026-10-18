# Research Workflow Skill · 科研工作流

将科研问题推进为可核查的文献证据、实验计划、真实结果与汇报材料。面向机器人／机床轨迹规划入门，也可用于其他需要证据和复现记录的研究任务。

**本项目按[MIT](LICENSE)开源。** 操作步骤、程序、推导及示例图表由本项目独立实现；科研入门主题受到[郭兰哲《科研入门指南》](https://github.com/LAMDA-NeSy/Research-Starter-Kit)启发，保留[作者主页](https://www.lamda.nju.edu.cn/guolz/)与[出处说明](ATTRIBUTION.md)。这是非官方实践项目，不含原指南正文、图片或附件。

## 先看实际示例

- [完整读图→配图教程](examples/figure-reading-and-design/README.md)：复制请求、查看输入图与解读、生成原创方法图和结果图、核查数据并写图注。
- [轨迹规划研究报告](examples/trajectory-planning/report.md)：单轴五次／七次固定多项式时间律，包含输入、推导、24份CSV、图形和检查结果。

![读图后制作的时长比较与变化率图](examples/figure-reading-and-design/generated/duration-tradeoff.png)

![研究工作流方法图](examples/figure-reading-and-design/generated/workflow-overview.png)

## 可以做什么

| 功能 | 你提供什么 | 主要产物 |
|---|---|---|
| 资料核查与阅读 | README、论文、图片或资料链接 | 作者与来源、实际阅读范围、许可与缺口 |
| 文献与研究定界 | 方向、已有论文、约束与资源 | 检索记录、证据卡、可证伪问题、公平基线 |
| 实验与复现 | 问题、参数、数据与验收指标 | 实际输出、运行条件、散列及质量检查 |
| 读图与配图 | 参考图、自有数据及目标用途 | 图意解读、图形设计、原创成图和图注 |
| 写作与讨论 | 真实进展、实验结果或审稿意见 | 论文段落、Meeting材料或逐条回应草稿 |

检索、阅读和写作需要助手及相应工具执行。随附数值程序使用Python标准库，可独立离线运行；安装Skill不会自行获取全文、运行硬件或发布成果。

## 使用Skill

### 无需安装的体验方式

下载仓库并解压，在能读取文件的助手中打开该目录，发送：

```text
请先读取 skills/research-workflow/SKILL.md，按其流程处理任务。
我的方向是机器人／机床运动控制轨迹规划，想研究jerk约束与运动平滑性。
请形成一个一周内可验证的问题，列出条件、假设、公平基线、指标和缺失资料。
先完成研究计划，不启动硬件。
```

### 安装到支持本地Skill的环境

将整个 `skills/research-workflow` 文件夹放入项目的 `.agents/skills/research-workflow`。在支持显式调用的客户端中使用 `$research-workflow`。客户端的发现位置和调用方式以[官方技能说明](https://learn.chatgpt.com/docs/build-skills)为准。

PowerShell示例，在仓库根目录执行；目标目录若已存在，先检查其中内容：

```powershell
$researchSkillTarget = Join-Path (Get-Location) '.agents\skills\research-workflow'
if (Test-Path -LiteralPath $researchSkillTarget) { throw '目标技能目录已存在，请先检查。' }
New-Item -ItemType Directory -Force (Split-Path $researchSkillTarget) | Out-Null
Copy-Item -LiteralPath '.\skills\research-workflow' -Destination $researchSkillTarget -Recurse
```

## 功能使用请求与预期输出

### 资料、图片与附件

```text
使用 $research-workflow。请核查我给出的资料，图片、表格、附件及直接内容外链也要读。
每项记录作者、正文/图片/页码范围、许可和缺口，需要登录时通知我。
不要把目录、摘要或短暂试看记为完整阅读。
```

产物是逐项来源清单及实际阅读记录。单一抓取方式失败时继续用可用的正常浏览器核查；明确受限的材料保留缺口。公开版不提供第三方指南全文或详尽替代摘要。

### 文献与研究问题

```text
使用 $research-workflow。我的任务是单轴静止到静止，行程100 mm，
速度≤0.5 m/s、加速度≤1 m/s²、jerk≤20 m/s³。
请区分路径时间参数化与状态到状态生成，建立种子文献卡，
把问题缩小到可验证的比较；未读论文正文的细节不要编造。
```

产物包括任务分类、检索串、来源与阅读范围、假设、候选基线和反例。没有系统检索时不声称首次或研究空白。

### 实际运行与质量核查

在仓库根目录执行（Python 3.10+，无需安装第三方Python包）：

```text
python skills/research-workflow/scripts/trajectory_benchmark.py --input skills/research-workflow/assets/trajectory-input.json --output rerun/default
python skills/research-workflow/scripts/verify_trajectory.py --input skills/research-workflow/assets/trajectory-input.json --output rerun/default
```

默认输入含1/10/100/1000 mm、反向100 mm和零行程。输出包括24份CSV、两个SVG、JSON结果、报告、清单及201项数值检查。复现[已保存结果](examples/trajectory-planning/report.md)时要区分新运行时间与历史记录。

要改变参数，可复制默认JSON到新文件，修改 `limits.velocity`、`limits.acceleration`、`limits.jerk` 和 `cases` 的 `start` / `end`，再以 `--input` 指向该文件。计算单位为米、秒及相应导数单位；限值须为正有限数，JSON用UTF-8保存。案例ID需唯一，输入字段详见 [默认输入](skills/research-workflow/assets/trajectory-input.json)。

输出目录应为空，或是同一输入的既有运行目录；脚本没有强制覆盖选项。不能让输出目录包含输入文件。自定义输入报告中的复现说明仍可能展示默认路径，重跑时以实际命令和manifest为准。

### 读图后制作自己的图

```text
使用 $research-workflow。请查看 examples/trajectory-planning/ 中两张PNG，
并核对summary.json与CSV。先解释比较条件、单位、图例和结论边界；
再用这些真实数据制作方法流程图和变化率图，保留可编辑SVG、图注与重跑步骤。
不要添加虚构误差条，不要把示意图当硬件证据。
```

[完整图文示例](examples/figure-reading-and-design/README.md)已实际执行。独立生成其原创SVG：

```text
python examples/figure-reading-and-design/make_figures.py --summary examples/trajectory-planning/summary.json --output rerun/figure-reading-and-design
```

该程序输出两张SVG、CSV、检查JSON和清单；仓库另提供实际渲染的PNG预览。程序不自动导出PNG，SVG与数据输出可确定性重跑。

### Meeting、摘要与审稿回应

```text
使用 $research-workflow。根据已有轨迹结果准备导师讨论材料：
项目目标、上次行动、新观察、候选原因、已试方案、两个待决策问题与下一周验收任务。
没有完成的实验请写计划，不要写成已经做过。
```

```text
使用 $research-workflow。审稿意见是“未证明全局时间最优，未提供硬件实验”。
请检查当前证据，列出应承认的边界、可澄清内容与需要补充的工作，再写回应。
先核查目标会议的回应规则，不虚构新增实验。
```

相关步骤见 [写作与讨论](skills/research-workflow/references/writing-and-discussion.md)。参会、奖学金等仅按实际请求处理，需另查当届主办方，不自动提交材料。

## 科学结论的范围

100 mm时，五次／七次固定形状的最小时长约0.759836／0.866787 s；七次约增加14.08%。1/10 mm时七次约减少4.35%，1000 mm时约增加16.67%。这些是相同运动学上限下的特定固定形状族比较，不是一般轨迹的全局最优性结论。

五次与静止段连接为C²，拼接处经典jerk不存在；七次为C³。jerk约束按运动区间单侧／几乎处处界解释。此例没有验证多轴、NURBS、扭矩、闭环振动或加工质量改善，也未实现或比较Ruckig等第三方算法。

## 验证与文件导航

运行现有数值测试和公开包检查：

```text
python -m unittest discover -s tests -v
python tools/check_release.py --public
```

[VALIDATION.md](VALIDATION.md)记录本版本实际检查，[PUBLIC_RELEASE_REVIEW.md](PUBLIC_RELEASE_REVIEW.md)说明公开范围。原实验的13项单元测试、201项数值检查与绘图检查分别记录，不能相加成不同科研发现。

| 路径 | 内容 |
|---|---|
| [Skill入口](skills/research-workflow/SKILL.md) | 助手按需执行的工作流 |
| [工作流记录](skills/research-workflow/references/workflow.md) | 研究卡、证据卡、实验与复盘 |
| [图表步骤](skills/research-workflow/references/figure-workflow.md) | 图意、数据、版式及素材条件 |
| [轨迹实验](examples/trajectory-planning/report.md) | 推导、输入输出、图表和局限 |
| [读图配图示例](examples/figure-reading-and-design/README.md) | 从输入图到原创成图的完整过程 |
| [出处与许可边界](ATTRIBUTION.md) | 原作者链接、原创内容范围和第三方材料边界 |

可选：有MATLAB时可运行 `tools/render_figures.m` 重绘已有数据；它不是核心计算依赖。MATLAB PNG与标准库SVG的布局和部分轴尺度不同，不能视为像素相同的文件。

## 许可与贡献

原创内容采用[MIT许可](LICENSE)，可按许可使用、修改和分发。外链原作、论文、品牌及图库不因此获得本项目授权。请勿提交未获许可的全文、截图、附件、身份凭据或真实机器私有数据；新增计算应保留输入、检查及明确边界。
