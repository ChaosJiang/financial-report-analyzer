# Chris Skills

Skills shared by Chris for improving daily work efficiency with Claude Code / Amp.

## Prerequisites

- Python 3.11+ installed
- Ability to run `python3` and `pip` commands

## Installation

### Quick Install (Recommended)

```bash
npx add-skill chaosjiang/chris-skills
```

### Register as Plugin Marketplace

Run the following command in Claude Code:

```bash
/plugin marketplace add chaosjiang/chris-skills
```

### Install Skills

**Option 1: Via Browse UI**

1. Select **Browse and install plugins**
2. Select **chris-skills**
3. Select **chris-stock-master**
4. Select **Install now**

**Option 2: Direct Install**

```bash
/plugin install chris-skills@chris-skills
```

**Option 3: Ask the Agent**

Simply tell Claude Code:

> Please install Skills from github.com/ChaosJiang/chris-skills

## Update Skills

To update skills to the latest version:

1. Run `/plugin` in Claude Code
2. Switch to **Marketplaces** tab (use arrow keys or Tab)
3. Select **chris-skills**
4. Choose **Update marketplace**

You can also **Enable auto-update** to get the latest versions automatically.

## Available Skills

### chris-stock-master

分析全球上市公司财报（美/日/港/A股），生成估值分析和投资报告。

```bash
# Analyze Apple
分析 AAPL

# Analyze Tencent
分析 0700.HK

# Analyze Kweichow Moutai
分析 600519.SH

# Analyze Toyota
分析 7203.T
```

**Supported Markets:**

| Market | Format | Example |
|--------|--------|---------|
| US | `SYMBOL` | AAPL, MSFT, GOOGL |
| Japan | `CODE.T` | 7203.T (Toyota) |
| China A | `CODE.SH/SZ` | 600519.SH (Moutai) |
| Hong Kong | `CODE.HK` | 0700.HK (Tencent) |

## Disclaimer

This skill provides analysis for reference only and does not constitute investment advice.

## License

MIT
