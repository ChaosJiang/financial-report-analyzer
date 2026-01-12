# Financial Report Analyzer Skill

用于分析上市公司财报与股价数据，生成业务与竞争分析、估值指标、分析师预期、可视化图表与结构化报告。支持美股、日股、A股、港股，并可在 OpenCode / Claude 中作为 Skill 使用。

## 功能说明
- 自动获取近 3-5 年财报与股价数据
- 财务指标分析（YoY、CAGR、利润率、ROE、ROA）
- 估值深度分析（P/E 分位数、PEG、EV/EBITDA、DCF 参考）
- 分析师预期（目标价、评级分布、近 90 天变动）
- PNG 图表输出（收入/利润、利润率、ROE/ROA、负债率、股价）
- 自动生成 Markdown 报告

## 安装方式
1. 克隆仓库

```bash
git clone <your-repo-url>
cd financial-report-analyzer
```

2. 创建 Skill 发现链接（OpenCode）

```bash
mkdir -p ~/.opencode/skill
ln -s "/Users/zhichaojiang/Document/GitHub/financial-report-analyzer" \
  ~/.opencode/skill/financial-report-analyzer
```

3. 创建虚拟环境并安装依赖

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r scripts/requirements.txt
```

4. 可选 API Key（按需）

```bash
export ALPHA_VANTAGE_API_KEY=...
export FMP_API_KEY=...
export TUSHARE_TOKEN=...
```

## 开发
- 主入口脚本都在 `scripts/` 中
- 每个步骤是独立脚本，可单独运行或串联

示例流程：

```bash
python scripts/fetch_data.py --symbol AAPL --market US --years 5 --output output
python scripts/analyze.py --input output/AAPL_data.json --output output
python scripts/valuation.py --input output/AAPL_data.json --analysis output/AAPL_analysis.json --output output
python scripts/analyst.py --input output/AAPL_data.json --output output
python scripts/visualize.py --analysis output/AAPL_analysis.json --output output/AAPL_charts
python scripts/report.py --analysis output/AAPL_analysis.json --valuation output/AAPL_valuation.json --analyst output/AAPL_analyst.json --output output
```

## 测试方式
端到端示例（AAPL）：

```bash
. .venv/bin/activate
python scripts/fetch_data.py --symbol AAPL --market US --years 5 --output output
python scripts/analyze.py --input output/AAPL_data.json --output output
python scripts/valuation.py --input output/AAPL_data.json --analysis output/AAPL_analysis.json --output output
python scripts/analyst.py --input output/AAPL_data.json --output output
python scripts/visualize.py --analysis output/AAPL_analysis.json --output output/AAPL_charts
python scripts/report.py --analysis output/AAPL_analysis.json --valuation output/AAPL_valuation.json --analyst output/AAPL_analyst.json --output output
```

输出文件位置：
- `output/AAPL_data.json`
- `output/AAPL_analysis.json`
- `output/AAPL_valuation.json`
- `output/AAPL_analyst.json`
- `output/AAPL_report.md`
- `output/AAPL_charts/*.png`

## 免责声明
本项目仅用于数据分析与研究参考，不构成任何投资建议。
