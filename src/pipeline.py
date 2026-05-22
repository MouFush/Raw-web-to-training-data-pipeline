"""
主流水线 (Pipeline)
===================
整合 HTML 清洗、内容过滤、大数据去重三大模块，
提供端到端的 Common Crawl → 训练数据 处理流程。

执行流程:
    ┌─────────────────┐
    │  输入: HTML 文件  │
    └────────┬────────┘
             ↓
    ┌─────────────────┐
    │  1. HTML 清洗    │ → HTMLCleaner.clean()
    │     提取正文      │
    └────────┬────────┘
             ↓ (success)
    ┌─────────────────┐
    │  2. 内容过滤      │ → ContentFilter.filter()
    │   安全+质量+语言   │
    └────────┬────────┘
             ↓ (passed)
    ┌─────────────────┐
    │  3. 数据去重      │ → Deduplicator.check()
    │  精确+近似去重    │
    └────────┬────────┘
             ↓ (unique)
    ┌─────────────────┐
    │  输出: JSONL 文件 │
    └─────────────────┘
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from html_cleaner import HTMLCleaner
from content_filter import ContentFilter
from deduplication import Deduplicator


class DataPipeline:
    """
    数据处理流水线

    使用示例:
        pipeline = DataPipeline(target_language='en')
        pipeline.run('data/raw_html', 'data/output/clean.jsonl')
    """

    def __init__(
        self,
        target_language: str = 'en',
        min_text_length: int = 50,
        lsh_threshold: float = 0.85,
        save_intermediate: bool = False,
        intermediate_dir: Optional[str] = None,
        verbose: bool = True,
    ):
        """
        初始化流水线

        Args:
            target_language: 目标语言代码 (en, zh, ja 等)
            min_text_length: 最小文本长度
            lsh_threshold: LSH 相似度阈值
            save_intermediate: 是否保存中间结果
            intermediate_dir: 中间结果目录
            verbose: 是否打印详细信息
        """
        self.target_language = target_language
        self.save_intermediate = save_intermediate
        self.verbose = verbose

        self.html_cleaner = HTMLCleaner(min_text_length=min_text_length)
        self.content_filter = ContentFilter(
            target_language=target_language
        )
        self.deduplicator = Deduplicator(lsh_threshold=lsh_threshold)

        self.intermediate_dir = None
        if save_intermediate:
            self.intermediate_dir = (
                Path(intermediate_dir) if intermediate_dir
                else Path('data/intermediate')
            )
            self.intermediate_dir.mkdir(parents=True, exist_ok=True)

        self.reset_stats()

    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'start_time': None,
            'end_time': None,
            'total_input': 0,
            'clean_failed': 0,
            'filter_failed': 0,
            'duplicates': 0,
            'output': 0,
        }

    def _log(self, message: str):
        """条件打印日志"""
        if self.verbose:
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] {message}")

    def process_document(
        self, doc_id: str, html_content: str
    ) -> Optional[Dict[str, Any]]:
        """
        处理单个 HTML 文档

        Args:
            doc_id: 文档唯一标识
            html_content: 原始 HTML 字符串

        Returns:
            dict 或 None:
            {
                'id': str,
                'text': str,
                'length': int,
                'word_count': int,
            }
            或被过滤返回 None
        """
        self.stats['total_input'] += 1

        clean_result = self.html_cleaner.clean(html_content)
        if not clean_result['success']:
            self.stats['clean_failed'] += 1
            if self.save_intermediate:
                self._save_failed(doc_id, clean_result, stage='clean')
            return None

        text = clean_result['text']

        filter_result = self.content_filter.filter(text)
        if not filter_result['passed']:
            self.stats['filter_failed'] += 1
            if self.save_intermediate:
                self._save_failed(doc_id, filter_result, stage='filter')
            return None

        dedup_result = self.deduplicator.check(doc_id, text)
        if dedup_result['is_duplicate']:
            self.stats['duplicates'] += 1
            return None

        self.stats['output'] += 1
        return {
            'id': doc_id,
            'text': text,
            'length': len(text),
            'word_count': len(text.split()),
        }

    def _save_failed(self, doc_id: str, result: Dict, stage: str):
        """保存未通过的文档用于调试"""
        if not self.intermediate_dir:
            return
        failed_dir = self.intermediate_dir / 'failed' / stage
        failed_dir.mkdir(parents=True, exist_ok=True)
        reason_path = failed_dir / f'{doc_id}_reason.json'
        with open(reason_path, 'w', encoding='utf-8') as f:
            json.dump({
                'doc_id': doc_id,
                'stage': stage,
                'result': {k: str(v) for k, v in result.items()}
            }, f, ensure_ascii=False)

    def process_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """处理单个 HTML 文件"""
        path = Path(file_path)
        doc_id = path.stem
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                html = f.read()
            return self.process_document(doc_id, html)
        except Exception as e:
            self._log(f"Error reading {file_path}: {e}")
            return None

    def run(
        self,
        input_dir: str,
        output_file: str,
        pattern: str = '*.html',
    ) -> List[Dict[str, Any]]:
        """
        批量运行流水线

        Args:
            input_dir: 输入目录 (包含 HTML 文件)
            output_file: 输出 JSONL 文件路径
            pattern: 文件匹配模式

        Returns:
            list: 处理成功的结果列表
        """
        self.reset_stats()
        self.stats['start_time'] = time.time()

        input_path = Path(input_dir)
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        html_files = sorted(input_path.glob(pattern))

        if not html_files:
            self._log(f"No files found matching '{pattern}' in {input_path}")
            return []

        self._log(f"Found {len(html_files)} HTML files to process")
        self._log(f"Pipeline: HTML Clean → Content Filter → Dedup → Output")
        self._log("-" * 50)

        results = []
        batch_size = 100

        for i, html_file in enumerate(html_files):
            result = self.process_file(str(html_file))
            if result:
                results.append(result)

            if (i + 1) % batch_size == 0:
                self._log(
                    f"Progress: {i+1}/{len(html_files)} "
                    f"(output: {len(results)})"
                )

        with open(output_path, 'w', encoding='utf-8') as f:
            for item in results:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

        self.stats['end_time'] = time.time()
        self.print_summary(output_path)
        return results

    def print_summary(self, output_path: Path = None):
        """打印处理摘要"""
        elapsed = self.stats['end_time'] - self.stats['start_time']
        total = self.stats['total_input']
        output = self.stats['output']

        print()
        print("=" * 60)
        print("  PIPELINE SUMMARY")
        print("=" * 60)
        print(f"  Total input:        {total:>8}")
        print(f"  HTML clean failed:  {self.stats['clean_failed']:>8}")
        print(f"  Content filtered:   {self.stats['filter_failed']:>8}")
        print(f"  Duplicates removed: {self.stats['duplicates']:>8}")
        print(f"  {'─' * 30}")
        print(f"  Final output:       {output:>8}")
        print(f"  Retention rate:     {output/total*100:>7.1f}%"
              if total > 0 else "  N/A")
        print(f"  Time elapsed:       {elapsed:>7.1f}s")
        print("=" * 60)

        dedup_stats = self.deduplicator.get_stats()
        print("\n  DEDUPLICATION DETAILS")
        print(f"  Exact duplicates:   "
              f"{dedup_stats['exact_duplicates']:>8}")
        print(f"  Approx duplicates:  "
              f"{dedup_stats['approx_duplicates']:>8}")
        print(f"  Dedup rate:         "
              f"{dedup_stats['dedup_rate']*100:>7.1f}%")

        if output_path:
            print(f"\n  Output saved to: {output_path}")


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("Usage: python pipeline.py <input_dir> <output_file>")
        print("Example: python pipeline.py data/raw_html data/output/clean.jsonl")
    else:
        pipeline = DataPipeline(
            target_language='en',
            save_intermediate=True,
            verbose=True
        )
        pipeline.run(sys.argv[1], sys.argv[2])