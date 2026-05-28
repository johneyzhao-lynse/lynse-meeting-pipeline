# Lynse Meeting Pipeline

从会议录音转写文本生成结构化摘要的 Python CLI 流水线。自动分类场景与行业，组装模块化 LLM prompt，调用 OpenAI 兼容 API（默认 DeepSeek），并内置敏感内容安全检测与自动重试。所有 UI 和 prompt 均为中文。

## 功能特性

- **智能分类路由** — 关键词规则引擎 + LLM 路由，自动匹配行业和总结模板
- **用户画像增强** — 按角色、行业、会议场景、风格偏好个性化 prompt
- **35+ 总结模板** — 覆盖金融、法律、地产、咨询、技术面试等场景
- **14 个行业提示词** — 建筑、教育、半导体、文旅等行业专属增强
- **敏感内容安全** — 政治、自害、亵渎、隐私四类本地正则扫描，支持 auto / strict / reactive / off 四种模式
- **飞轮质量闭环** — 反馈记录 → 推理分析 → prompt 改进建议
- **交互式 TUI** — Rich + Prompt Toolkit 驱动的引导式总结向导

## 快速开始

### 环境要求

- Python 3.10+
- 无外部核心依赖（纯 stdlib）
- TUI 需要 `rich` 和 `prompt_toolkit`

### 安装

```bash
git clone https://github.com/johneyzhao-lynse/lynse-meeting-pipeline.git
cd lynse-meeting-pipeline
python -m venv .venv
.venv/bin/pip install rich prompt_toolkit
```

### 配置

创建 `config/agent.local.json`（已 gitignore）：

```json
{
  "model": "deepseek-chat",
  "base_url": "https://api.deepseek.com",
  "api_key": "your-api-key"
}
```

也可通过环境变量配置：`LYNCLAW_AGENT_MODEL`、`LYNCLAW_AGENT_BASE_URL`、`LYNCLAW_AGENT_API_KEY`。

## 使用方式

### 交互式 TUI

```bash
python tools/lynse.py
```

引导式向导，逐步选择转写文本、模板、行业、模型参数。

### 命令行

```bash
# 自动路由模式（分类器自动选择模板）
python tools/lynclaw_agent.py --auto-route --transcript <file>

# 手动指定行业和模板
python tools/lynclaw_agent.py --industry <file> --template <file> --transcript <file>

# Dry run（仅预览请求，不调用 API）
python tools/lynclaw_agent.py --auto-route --transcript <file> --dry-run

# 列出可用的行业、模板、转写文本
python tools/lynclaw_agent.py --list
```

### 独立分类器

```bash
python tools/run_classifier.py --transcript <file> --json
```

### 验证用户 prompt 文件

```bash
python tools/validate_user_prompt.py --user-prompt-file <path>
```

### 飞轮分析

```bash
python tools/run_flywheel_analysis.py \
  --samples-json <path> \
  --feedback-json <path> \
  --analysis-goal <text> \
  [--dry-run]
```

## 主要参数

| 参数 | 说明 |
|------|------|
| `--auto-route` | 自动分类并路由到匹配模板 |
| `--transcript` | 转写文本文件名或绝对路径 |
| `--industry` | 行业增强 prompt 文件名 |
| `--template` | 总结模板文件名 |
| `--model` | 模型 ID（默认 deepseek-chat） |
| `--safety-mode` | 安全模式：auto / strict / reactive / off |
| `--dry-run` | 仅预览请求 payload |
| `--user-prompt-file` | 用户自定义 prompt markdown 文件 |
| `--user-prompt-profile` | 用户画像配置名称 |
| `--thinking` | 深度思考模式：enabled / disabled |
| `--reasoning-effort` | 推理强度：low / medium / high |
| `--list` | 列出可用资源 |

完整参数列表请参考 `python tools/lynclaw_agent.py --help`。

## 项目结构

```
├── tools/                    # 入口脚本
│   ├── lynclaw_agent.py      # CLI 主入口
│   └── lynse.py              # TUI 入口
├── runtime/                  # 核心运行时
│   ├── cli.py                # CLI 参数解析与流程编排
│   ├── messages.py           # 系统消息与 prompt 组装
│   ├── client.py             # OpenAI 兼容 API 客户端（urllib）
│   ├── safety.py             # 敏感内容检测与处理
│   ├── failure_detector.py   # 错误分类与重试判断
│   ├── classifier/           # 会议分类引擎
│   ├── user_prompt/          # 用户 prompt 解析与编译
│   ├── flywheel/             # 飞轮质量闭环
│   ├── tui/                  # 交互式 TUI
│   └── agent/                # 配置加载
├── assets/                   # 模块化 prompt 资产
│   ├── prompts/              # 系统 prompt、行业增强、安全约束
│   ├── templates/summary/    # 35+ 总结模板
│   └── manifests/            # 模板与行业路由清单
├── config/                   # 配置文件（gitignore）
├── examples/                 # 示例数据与输出
│   ├── transcripts/          # 转写文本样本
│   ├── outputs/              # 生成结果
│   └── run-logs/             # 运行日志
└── tests/                    # 测试（unittest）
```

## 测试

```bash
# 运行全部测试
python -m unittest discover -s tests -v

# 运行单个测试文件
python -m unittest tests/test_reactive_safety.py -v
```

## 支持的行业

建筑、咨询、文旅、电商零售、教育培训、理财规划、政务、保险、投融资、IT 互联网、法律、市场营销、房地产、半导体芯片。

## License

Private — 内部使用
