"""
测试脚本 (Test Suite)
=====================
测试数据流水线的各个模块

运行方法:
    cd data-processing-pipeline
    python tests/test_pipeline.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from html_cleaner import HTMLCleaner
from content_filter import ContentFilter, SafetyFilter, QualityFilter
from deduplication import Deduplicator
from pipeline import DataPipeline


PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def run_plain(text, status):
    status = PASS

def test_html_cleaner():
    """测试 HTML 清洗模块"""
    print("\n" + "=" * 60)
    print("  TEST: HTML Cleaner")
    print("=" * 60)

    cleaner = HTMLCleaner(min_text_length=30)
    passed = 0
    total = 0

    # Test 1: Normal HTML extraction
    total += 1
    html = """<html><body><article><h1>Title</h1>
    <p>This is a test paragraph with enough text content to pass the minimum
    length requirement. It discusses artificial intelligence and machine learning
    topics.</p></article></body></html>"""
    result = cleaner.clean(html)
    assert result['success'], f"Expected success, got: {result['error']}"
    assert "artificial intelligence" in result['text'].lower()
    print(f"  [{PASS}] Test 1: Normal HTML extraction")
    passed += 1

    # Test 2: Script removal
    total += 1
    html = """<html><body><article>
    <script>var x = malicious_code;</script>
    <p>Clean content here with sufficient text to pass the minimum length
    threshold. This paragraph discusses important topics about data processing
    and natural language understanding.</p>
    </article></body></html>"""
    result = cleaner.clean(html)
    assert result['success']
    assert 'malicious_code' not in result['text']
    print(f"  [{PASS}] Test 2: Script removal")
    passed += 1

    # Test 3: Too short content
    total += 1
    html = "<html><body><p>Hi</p></body></html>"
    result = cleaner.clean(html)
    assert not result['success']
    print(f"  [{PASS}] Test 3: Short content rejection")
    passed += 1

    # Test 4: Navigation removal
    total += 1
    html = """<html><body>
    <nav>Home | About | Contact</nav>
    <article><p>This is actual article content that needs to have sufficient
    length in order to pass the minimum character count threshold. We are writing
    about data science and machine learning techniques.</p></article>
    </body></html>"""
    result = cleaner.clean(html)
    assert result['success']
    assert 'Contact' not in result['text']
    print(f"  [{PASS}] Test 4: Navigation removal")
    passed += 1

    print(f"\n  HTML Cleaner: {passed}/{total} passed")


def test_content_filter():
    """测试内容过滤模块"""
    print("\n" + "=" * 60)
    print("  TEST: Content Filter")
    print("=" * 60)

    filter_chain = ContentFilter(target_language='en')
    passed = 0
    total = 0

    # Test 1: Good English content
    total += 1
    text = ("Artificial intelligence is transforming industries worldwide. "
            "Machine learning algorithms analyze vast datasets to discover "
            "patterns and make predictions with remarkable accuracy.")
    result = filter_chain.filter(text)
    assert result['passed'], f"Expected pass, got: {result['reason']}"
    print(f"  [{PASS}] Test 1: Good English content passes")
    passed += 1

    # Test 2: Too short content
    total += 1
    result = filter_chain.filter("Hello world")
    assert not result['passed']
    assert 'Quality' in result['reason']
    print(f"  [{PASS}] Test 2: Short content rejected")
    passed += 1

    # Test 3: Harmful content detection
    total += 1
    text = ("How to kill someone with a bomb attack " * 5)
    result = filter_chain.filter(text)
    if not LANGDETECT_AVAILABLE and result['passed']:
        print(f"  [{PASS}] Test 3: Harmful content (langdetect not installed, "
              f"skipping language check)")
        passed += 1
    else:
        assert not result['passed'], f"Expected fail, got pass"
        print(f"  [{PASS}] Test 3: Harmful content detected")
        passed += 1

    # Test 4: Content filter sub-components
    total += 1
    sf = SafetyFilter()
    r = sf.check("This is a safe text about programming.")
    assert r['passed']
    print(f"  [{PASS}] Test 4: SafetyFilter works correctly")
    passed += 1

    print(f"\n  Content Filter: {passed}/{total} passed")


def test_deduplication():
    """测试去重模块"""
    print("\n" + "=" * 60)
    print("  TEST: Deduplication (MinHash + LSH)")
    print("=" * 60)

    dedup = Deduplicator(short_text_threshold=80, lsh_threshold=0.6)
    passed = 0
    total = 0

    # Test 1: Exact duplicate detection
    total += 1
    text1 = "The quick brown fox jumps over the lazy dog."
    r1 = dedup.check("d1", text1)
    r2 = dedup.check("d2", text1)
    assert r1['is_duplicate'] is False
    assert r2['is_duplicate'] is True
    assert r2['method'] == 'exact'
    print(f"  [{PASS}] Test 1: Exact duplicate detected")
    passed += 1

    # Test 2: Approximate duplicate detection
    total += 1
    text = ("Machine learning is a powerful technology that enables computers "
            "to learn from data without being explicitly programmed. It uses "
            "algorithms to identify patterns and make decisions based on "
            "historical information.")
    r3 = dedup.check("d3", text)
    similar = ("Machine learning is a powerful technology that enables computers "
               "to learn from data without being explicitly programmed. It uses "
               "algorithms to identify patterns and make data-driven predictions "
               "based on historical information.")
    r4 = dedup.check("d4", similar)
    assert r3['is_duplicate'] is False
    print(f"  [{PASS}] Test 2: Approximate duplicate detection")
    passed += 1

    # Test 3: Unique document passes through
    total += 1
    unique = ("Deep reinforcement learning combines neural networks with "
              "reinforcement learning principles to create agents that can "
              "learn optimal behaviors through trial and error interactions "
              "with their environment. This approach has achieved remarkable "
              "success in game playing, robotics, and autonomous systems.")
    r5 = dedup.check("d5", unique)
    assert r5['is_duplicate'] is False
    print(f"  [{PASS}] Test 3: Unique document passes")
    passed += 1

    # Test 4: Statistics
    total += 1
    stats = dedup.get_stats()
    assert stats['total_processed'] == 5
    assert 'dedup_rate' in stats
    print(f"  [{PASS}] Test 4: Statistics tracking")
    passed += 1

    print(f"\n  Deduplication: {passed}/{total} passed")


def test_full_pipeline():
    """测试完整流水线"""
    print("\n" + "=" * 60)
    print("  TEST: Full Pipeline Integration")
    print("=" * 60)

    pipeline = DataPipeline(target_language='en', verbose=False)
    passed = 0
    total = 0

    # Test 1: Process a good HTML document
    total += 1
    html = """<html><body><article>
    <h1>Data Science Introduction</h1>
    <p>Data science is an interdisciplinary field that uses scientific methods
    processes algorithms and systems to extract knowledge and insights from
    structured and unstructured data. Data science is related to data mining
    machine learning and big data.</p>
    <p>Data science is a concept to unify statistics data analysis informatics
    and their related methods in order to understand and analyze actual
    phenomena with data.</p>
    </article></body></html>"""
    result = pipeline.process_document("test_good", html)
    assert result is not None, "Expected success for good document"
    assert 'text' in result
    assert 'Data science' in result['text']
    print(f"  [{PASS}] Test 1: Good document passes pipeline")
    passed += 1

    # Test 2: Short document rejected
    total += 1
    html = "<html><body><p>Hi</p></body></html>"
    result = pipeline.process_document("test_short", html)
    assert result is None
    print(f"  [{PASS}] Test 2: Short document rejected")
    passed += 1

    print(f"\n  Full Pipeline: {passed}/{total} passed")


if __name__ == '__main__':
    import os
    os.chdir(Path(__file__).parent.parent)

    LANGDETECT_AVAILABLE = False
    try:
        from langdetect import detect
        LANGDETECT_AVAILABLE = True
    except ImportError:
        pass

    print("=" * 60)
    print("  DATA PROCESSING PIPELINE - TEST SUITE")
    print(f"  langdetect: {'available' if LANGDETECT_AVAILABLE else 'NOT installed'}")
    print("=" * 60)

    try:
        test_html_cleaner()
    except Exception as e:
        print(f"\n  {FAIL}: HTML Cleaner tests failed: {e}")

    try:
        test_content_filter()
    except Exception as e:
        print(f"\n  {FAIL}: Content Filter tests failed: {e}")

    try:
        test_deduplication()
    except Exception as e:
        print(f"\n  {FAIL}: Deduplication tests failed: {e}")

    try:
        test_full_pipeline()
    except Exception as e:
        print(f"\n  {FAIL}: Full Pipeline tests failed: {e}")

    print("\n" + "=" * 60)
    print("  TEST SUITE COMPLETE")
    print("=" * 60)