# Data Processing Pipeline

从原始网页 (Common Crawl HTML) 到高质量训练数据的完整数据处理流水线。

## 架构概览

```
原始 HTML → [HTML清洗] → [内容过滤] → [数据去重] → 高质量训练数据
                │               │              │
           BeautifulSoup   Safety/Quality    MinHash+LSH
                            /Language
```

## 项目结构

```
data-processing-pipeline/
├── src/
│   ├── __init__.py              # 包初始化
│   ├── html_cleaner.py          # 模块1: HTML 清洗
│   ├── content_filter.py        # 模块2: 内容过滤
│   ├── deduplication.py         # 模块3: 大规模去重
│   └── pipeline.py              # 完整流水线整合
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py         # 测试套件
├── data/
│   ├── raw_html/                # 输入: 原始 HTML 文件
│   └── output/                  # 输出: 清洗后的 JSONL 数据
├── run.py                       # 一键启动脚本
├── requirements.txt             # 依赖列表
├── .gitignore
└── README.md
```

## 环境配置

```bash
# 1. 激活 conda 环境
conda activate qwen3.5-alignment

# 2. 安装依赖
pip install -r requirements.txt
```

## 快速开始

```bash
# 生成测试数据并运行
python run.py --generate-samples

# 使用自定义配置运行
python run.py --input data/raw_html --output data/output/result.jsonl --language en

# 运行测试
python tests/test_pipeline.py
```

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--input`, `-i` | 输入目录 | `data/raw_html` |
| `--output`, `-o` | 输出文件路径 | `data/output/clean_data.jsonl` |
| `--language`, `-l` | 目标语言 | `en` |
| `--threshold`, `-t` | 去重相似度阈值 | `0.85` |
| `--min-length`, `-m` | 最小文本长度 | `50` |
| `--generate-samples`, `-g` | 生成测试数据 | - |
| `--save-intermediate` | 保存中间结果 | - |
| `--quiet`, `-q` | 静默模式 | - |

## 模块详解

### 1. HTML 清洗 (`html_cleaner.py`)

- **原理**: 使用 BeautifulSoup 解析 DOM 树，移除 script/style/nav/footer 等噪声标签
- **关键操作**: `decompose()` 彻底删除节点，`get_text()` 提取纯文本
- **输出**: 干净的结构化文本

### 2. 内容过滤 (`content_filter.py`)

- **安全过滤**: 正则关键词匹配（暴力/色情/仇恨言论）
- **质量过滤**: 信息熵 H = -Σ p(x)log₂(p(x)) 衡量字符分布
- **语言过滤**: langdetect 基于 n-gram 统计模型检测语言

### 3. 数据去重 (`deduplication.py`)

- **精确去重**: MD5 哈希，O(1) 查询
- **近似去重**: MinHash + LSH (局部敏感哈希)
  - Shingling: 文本 → k-gram 集合
  - MinHash: 集合 → 128 维签名向量
  - LSH: 签名分桶 → 高效候选检索

### 4. 流水线 (`pipeline.py`)

整合三个模块，提供端到端处理，支持批量处理和进度显示。

## 技术原理

### MinHash 定理

P(h_min(A) = h_min(B)) = J(A,B) = |A∩B| / |A∪B|

### LSH 概率

P(成为候选对) = 1 - (1 - s^r)^b

当 s=0.85, r=8, b=16: P ≈ 0.998
当 s=0.3, r=8, b=16: P ≈ 0.0016

### 复杂度

| 操作 | 暴力方法 | MinHash+LSH |
|------|----------|-------------|
| 去重查询 | O(n²) | O(n × k) |

## 输出格式

```jsonl
{"id": "doc_001", "text": "Clean text...", "length": 1234, "word_count": 200}
{"id": "doc_002", "text": "Another text...", "length": 567, "word_count": 89}
```