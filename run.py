"""
入口脚本 (Run Script)
====================
数据流水线的一键启动脚本

用法:
    python run.py
    python run.py --input data/custom_dir --output data/output/result.jsonl
    python run.py --language zh --threshold 0.8
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from pipeline import DataPipeline


def generate_sample_data(output_dir: str, num_docs: int = 10):
    """
    生成测试用的 HTML 样例数据

    包含多种场景:
    - 正常英文文章
    - 包含噪声标签的页面
    - 重复内容(用于测试去重)
    - 太短的内容
    - 非英语内容
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    en_article = """<!DOCTYPE html>
<html>
<head><title>Machine Learning Guide</title>
<script>console.log('tracking');</script>
<style>body{margin:0;padding:20px;font-family:Arial;}</style>
</head>
<body>
<nav>Home | Articles | About | Contact</nav>
<article>
<h1>Introduction to Machine Learning</h1>
<p>Machine learning is a subset of artificial intelligence that provides systems
the ability to automatically learn and improve from experience without being
explicitly programmed. Machine learning focuses on the development of computer
programs that can access data and use it to learn for themselves.</p>
<p>The process of learning begins with observations or data such as examples,
direct experience, or instruction in order to look for patterns in data and make
better decisions in the future based on the examples that we provide.</p>
<p>The primary aim is to allow the computers learn automatically without human
intervention or assistance and adjust actions accordingly.</p>
</article>
<footer>Copyright 2024 AI Learning Hub</footer>
</body>
</html>"""

    en_article2 = """<!DOCTYPE html>
<html>
<body>
<article>
<h1>Deep Learning Fundamentals</h1>
<p>Deep learning is a class of machine learning algorithms that uses multiple
layers to progressively extract higher-level features from the raw input. For
example, in image processing, lower layers may identify edges while higher
layers may identify the concepts relevant to a human such as digits or letters
or faces.</p>
<p>Deep learning models are based on artificial neural networks specifically
convolutional neural networks although they can also include propositional
formulas or latent variables organized layer-wise in deep generative models.</p>
</article>
</body>
</html>"""

    en_article3 = """<!DOCTYPE html>
<html>
<head><script>alert('ad');</script></head>
<body>
<aside>Advertisement: Buy Now!</aside>
<article>
<h1>Natural Language Processing Overview</h1>
<p>Natural language processing is a subfield of linguistics computer science
and artificial intelligence concerned with the interactions between computers
and human language. The goal is to enable computers to understand and process
human languages.</p>
<p>Modern NLP techniques are based on deep learning and large language models
that can perform tasks such as translation, summarization, and question
answering with remarkable accuracy.</p>
</article>
</body>
</html>"""

    short_page = """<!DOCTYPE html>
<html><body><p>Click here to win!</p></body></html>"""

    duplicate_page = en_article  # 与第一篇完全重复

    similar_page = """<!DOCTYPE html>
<html>
<body>
<article>
<h1>Introduction to Machine Learning</h1>
<p>Machine learning is a subset of artificial intelligence that provides systems
the ability to automatically learn and improve from experience without being
explicitly programmed.</p>
<p>The process of learning begins with observations or data such as examples
direct experience or instruction in order to look for patterns in data.</p>
</article>
</body>
</html>"""

    chinese_page = """<!DOCTYPE html>
<html>
<body>
<article>
<h1>机器学习入门指南</h1>
<p>机器学习是人工智能的一个重要分支，它使计算机系统能够从数据中自动学习和改进，
而无需进行明确的编程。机器学习算法通过分析大量数据来识别模式和规律。</p>
<p>深度学习的出现极大地推动了自然语言处理和计算机视觉等领域的发展。</p>
</article>
</body>
</html>"""

    noise_page = """<!DOCTYPE html>
<html>
<head>
<script>
var _gaq = _gaq || [];
_gaq.push(['_setAccount', 'UA-12345-1']);
(function() {
var ga = document.createElement('script');
ga.src = 'http://www.google-analytics.com/ga.js';
var s = document.getElementsByTagName('script')[0];
s.parentNode.insertBefore(ga, s);
})();
</script>
<style>
body {background: #fff; color: #333;}
.ad-banner {display: block; width: 100%;}
</style>
</head>
<body>
<header><div class="ad-banner">AD SPACE</div></header>
<nav><ul><li>Home</li><li>Products</li><li>About</li></ul></nav>
<div class="sidebar"><div class="ad-banner">ANOTHER AD</div></div>
<main>
<h1>Computer Vision Applications</h1>
<p>Computer vision is an interdisciplinary field that deals with how computers
can gain high-level understanding from digital images or videos. From the
perspective of engineering it seeks to automate tasks that the human visual
system can do.</p>
<p>Computer vision tasks include methods for acquiring processing analyzing and
understanding digital images and extraction of high-dimensional data from the
real world in order to produce numerical or symbolic information.</p>
</main>
<footer><p>Copyright 2024. Terms of Service. Privacy Policy.</p></footer>
</body>
</html>"""

    documents = [
        ("ml_guide", en_article),
        ("deep_learning", en_article2),
        ("nlp_overview", en_article3),
        ("short_page", short_page),
        ("ml_duplicate", duplicate_page),
        ("ml_similar", similar_page),
        ("chinese_ml", chinese_page),
        ("computer_vision", noise_page),
    ]

    for i, (doc_id, html) in enumerate(documents[:num_docs]):
        file_path = output_path / f"{doc_id}.html"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  Generated: {file_path}")

    print(f"\nGenerated {len(documents[:num_docs])} sample HTML files in {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Data Processing Pipeline - Common Crawl HTML to Training Data'
    )
    parser.add_argument(
        '--input', '-i',
        default='data/raw_html',
        help='Input directory containing HTML files (default: data/raw_html)'
    )
    parser.add_argument(
        '--output', '-o',
        default='data/output/clean_data.jsonl',
        help='Output JSONL file path (default: data/output/clean_data.jsonl)'
    )
    parser.add_argument(
        '--language', '-l',
        default='en',
        help='Target language filter (default: en)'
    )
    parser.add_argument(
        '--threshold', '-t',
        type=float,
        default=0.85,
        help='LSH similarity threshold for dedup (default: 0.85)'
    )
    parser.add_argument(
        '--min-length', '-m',
        type=int,
        default=50,
        help='Minimum text length (default: 50)'
    )
    parser.add_argument(
        '--generate-samples', '-g',
        action='store_true',
        help='Generate sample HTML test data before running'
    )
    parser.add_argument(
        '--num-samples', '-n',
        type=int,
        default=8,
        help='Number of sample documents to generate (default: 8)'
    )
    parser.add_argument(
        '--save-intermediate',
        action='store_true',
        help='Save intermediate results (failed documents) for debugging'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress detailed progress output'
    )

    args = parser.parse_args()

    if args.generate_samples:
        print("Generating sample HTML test data...")
        generate_sample_data(args.input, args.num_samples)

    input_path = Path(args.input)
    if not input_path.exists() or not list(input_path.glob('*.html')):
        print(f"\nNo HTML files found in '{args.input}'.")
        print("Use --generate-samples to create test data, or:")
        print("  1. Place your HTML files in data/raw_html/")
        print("  2. Run: python run.py")
        return

    pipeline = DataPipeline(
        target_language=args.language,
        min_text_length=args.min_length,
        lsh_threshold=args.threshold,
        save_intermediate=args.save_intermediate,
        verbose=not args.quiet,
    )

    print(f"\nStarting pipeline with config:")
    print(f"  Input:       {args.input}")
    print(f"  Output:      {args.output}")
    print(f"  Language:    {args.language}")
    print(f"  Min length:  {args.min_length}")
    print(f"  Threshold:   {args.threshold}")
    print()

    pipeline.run(args.input, args.output)


if __name__ == '__main__':
    main()