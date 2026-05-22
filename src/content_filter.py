"""
模块 2: 内容过滤器 (Content Filter)
==================================
对清洗后的文本进行多维度过滤，确保训练数据质量

子过滤器:
    SafetyFilter   - 有害内容过滤 (关键词匹配)
    QualityFilter  - 文本质量过滤 (熵/词长/重复度)
    LanguageFilter - 语言过滤 (n-gram 统计模型)

过滤流程:
    文本 → SafetyFilter → QualityFilter → LanguageFilter → 通过/拒绝

原理:
    - 关键词匹配: O(n) 扫描，快速初筛暴力/色情/仇恨内容
    - 信息熵: H = -Σ p(x)*log₂(p(x))，衡量字符分布均匀度
    - 语言检测: 基于 n-gram 频率特征与语言模型的匹配
"""

import re
import math
from collections import Counter
from typing import Dict, List

try:
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False


class ContentFilter:
    """
    内容过滤器

    组合三个子过滤器，按序执行:
    1. SafetyFilter    - 有害内容筛查
    2. QualityFilter   - 文本质量评估
    3. LanguageFilter  - 目标语言确认
    任一不通过即返回拒绝
    """

    def __init__(self, target_language: str = 'en'):
        self.safety_filter = SafetyFilter()
        self.quality_filter = QualityFilter()
        self.language_filter = LanguageFilter(target_language)

    def filter(self, text: str) -> Dict:
        """
        执行完整过滤

        Args:
            text: 待过滤文本

        Returns:
            dict: {
                'passed': bool       - 是否通过所有过滤
                'reason': str|None   - 未通过原因
                'details': dict      - 各子过滤器详情
            }
        """
        details = {}

        safety = self.safety_filter.check(text)
        details['safety'] = safety
        if not safety['passed']:
            return {
                'passed': False,
                'reason': f'Safety: {safety["reason"]}',
                'details': details
            }

        quality = self.quality_filter.check(text)
        details['quality'] = quality
        if not quality['passed']:
            return {
                'passed': False,
                'reason': f'Quality: {quality["reason"]}',
                'details': details
            }

        language = self.language_filter.check(text)
        details['language'] = language
        if not language['passed']:
            return {
                'passed': False,
                'reason': f'Language: {language["reason"]}',
                'details': details
            }

        return {
            'passed': True,
            'reason': None,
            'details': details
        }


class SafetyFilter:
    """
    有害内容过滤器

    使用正则表达式关键词匹配检测有害内容。
    关键词分为三个类别: 暴力、色情、仇恨言论。

    原理:
        正则表达式实现 O(n) 时间复杂度的文本扫描，
        匹配到的关键词会记录并作为拒绝理由返回。
    """

    CATEGORY_PATTERNS = {
        'violence': [
            r'\b(kill(ed|ing|er)?s?\b)',
            r'\b(murder(ed|ing|er)?s?\b)',
            r'\b(attack(ed|ing|er)?s?\b)',
            r'\b(bomb(ed|ing|er)?s?\b)',
            r'\b(terror(ism|ist)?s?\b)',
            r'\b(shoot(ing|er)?s?\b)',
            r'\b(weapon(ize)?s?\b)',
        ],
        'adult': [
            r'\b(porn(ography|ographic)?\b)',
            r'\b(xxx\b)',
            r'\b(sexual(ly)?\b)',
            r'\b(nude|naked|explicit)\b',
        ],
        'hate': [
            r'\b(hate\s?speech)\b',
            r'\b(racist|racism)\b',
            r'\b(nazi|supremacy|supremacist)\b',
        ],
    }

    def __init__(self):
        self.compiled = {}
        for category, patterns in self.CATEGORY_PATTERNS.items():
            self.compiled[category] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def check(self, text: str) -> Dict:
        """
        检查并记录匹配到的有害关键词
        """
        text_lower = text.lower()
        all_matches = []

        for category, patterns in self.compiled.items():
            for pattern in patterns:
                found = pattern.findall(text_lower)
                for f in found:
                    if isinstance(f, tuple):
                        all_matches.append(f[0])
                    else:
                        all_matches.append(f)

        if all_matches:
            unique_matches = list(set(all_matches))[:10]
            return {
                'passed': False,
                'reason': f'Harmful keywords: {unique_matches}',
                'matches': unique_matches
            }

        return {'passed': True, 'reason': None, 'matches': []}


class QualityFilter:
    """
    文本质量过滤器

    检查指标:
    1. 最小长度        - 过滤过短文段
    2. 字符熵值        - 过滤字符分布异常 (乱码/重复)
    3. 平均词长        - 过滤超长无意义字符串
    4. 行重复度        - 过滤大量重复行的文档

    熵值计算原理:
        H = -Σ p(x) * log₂(p(x))
        其中 p(x) 是字符 x 的出现概率
        熵值越高 → 字符分布越均匀 → 文本质量越高
    """

    def __init__(
        self,
        min_length: int = 100,
        min_entropy: float = 3.0,
        max_avg_word_len: int = 25,
        max_duplicate_line_ratio: float = 0.6
    ):
        self.min_length = min_length
        self.min_entropy = min_entropy
        self.max_avg_word_len = max_avg_word_len
        self.max_duplicate_line_ratio = max_duplicate_line_ratio

    def _calculate_entropy(self, text: str) -> float:
        """
        计算文本的信息熵

        公式: H = -Σ p(x) * log₂(p(x))
        """
        if not text:
            return 0.0
        char_counts = Counter(text)
        total = len(text)
        entropy = 0.0
        for count in char_counts.values():
            p = count / total
            entropy -= p * math.log2(p)
        return entropy

    def check(self, text: str) -> Dict:
        checks = []

        if len(text) < self.min_length:
            checks.append(f'Too short: {len(text)} < {self.min_length}')

        entropy = self._calculate_entropy(text)
        if entropy < self.min_entropy:
            checks.append(
                f'Low entropy: {entropy:.2f} < {self.min_entropy}'
            )

        words = text.split()
        if words:
            avg_word_len = sum(len(w) for w in words) / len(words)
            if avg_word_len > self.max_avg_word_len:
                checks.append(
                    f'High avg word length: {avg_word_len:.1f} > '
                    f'{self.max_avg_word_len}'
                )

        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if lines and len(lines) >= 5:
            line_counts = Counter(lines)
            most_common_count = line_counts.most_common(1)[0][1]
            dup_ratio = most_common_count / len(lines)
            if dup_ratio > self.max_duplicate_line_ratio:
                checks.append(
                    f'High duplicate line ratio: {dup_ratio:.2f}'
                )

        if checks:
            return {
                'passed': False,
                'reason': '; '.join(checks),
                'entropy': round(entropy, 2),
                'checks': checks
            }

        return {
            'passed': True,
            'reason': None,
            'entropy': round(entropy, 2),
            'checks': []
        }


class LanguageFilter:
    """
    语言过滤器

    使用 langdetect 库检测文本语言，只保留目标语言内容。

    原理:
        langdetect 基于 n-gram 频率分布进行语言检测。
        训练阶段统计各语言 n-gram 频率 → 建立语言模型。
        检测阶段提取文本 n-gram → 与模型比较 → 选择最匹配语言。

    优化:
        仅检测前 1000 字符，大幅提高速度，不影响准确率。
    """

    def __init__(self, target_language: str = 'en'):
        self.target_language = target_language

    def check(self, text: str) -> Dict:
        if not LANGDETECT_AVAILABLE:
            return {
                'passed': True,
                'reason': 'langdetect not installed',
                'detected': 'unknown'
            }

        try:
            sample = text[:1000]
            detected = detect(sample)

            if detected == self.target_language:
                return {
                    'passed': True,
                    'reason': None,
                    'detected': detected
                }
            else:
                return {
                    'passed': False,
                    'reason': (
                        f'Expected {self.target_language}, '
                        f'got {detected}'
                    ),
                    'detected': detected
                }

        except Exception as e:
            return {
                'passed': False,
                'reason': str(e),
                'detected': 'error'
            }


if __name__ == '__main__':
    filter_chain = ContentFilter(target_language='en')

    test_cases = [
        (
            "good",
            "Artificial intelligence is transforming the way we work and "
            "live. Machine learning algorithms can now process vast amounts "
            "of data to find patterns and make predictions."
        ),
        (
            "too_short",
            "Hello world"
        ),
        (
            "harmful",
            "This is a guide on how to make a bomb and attack people "
            "with weapons."
        ),
        (
            "repetitive",
            "Hello world. Hello world. Hello world. Hello world. "
            "Hello world. Hello world. Hello world."
        ),
    ]

    print("=" * 60)
    print("Content Filter - Test Results")
    print("=" * 60)
    for name, text in test_cases:
        result = filter_chain.filter(text)
        status = "PASS" if result['passed'] else "FAIL"
        print(f"\n[{name}] {status}")
        print(f"  Reason: {result['reason']}")