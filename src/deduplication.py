"""
模块 3: 大规模数据去重 (Deduplication)
====================================
使用 MinHash + LSH 实现高效近似去重

核心算法:
    ┌─────────────────────────────────────────────────────┐
    │  1. Shingling: 文本 → k-gram 集合 S(d)              │
    │  2. MinHash:   集合 → 签名向量 sig(d) (128维)        │
    │  3. LSH:       签名 → 分桶索引 (b个band)             │
    │  4. Query:     新文档 → 查同桶候选 → 验证相似度       │
    └─────────────────────────────────────────────────────┘

MinHash 定理:
    P(h_min(A) = h_min(B)) = J(A,B) = |A∩B| / |A∪B|
    即: 两个集合 MinHash 值相等的概率等于其 Jaccard 相似度

LSH 概率:
    P(成为候选对) = 1 - (1 - s^r)^b
    其中 s 是 Jaccard 相似度, r 是 band 行数, b 是 band 数量

    当 s=0.85, r=8, b=16:
        P ≈ 1 - (1 - 0.85^8)^16 ≈ 1 - (1 - 0.27)^16 ≈ 0.998

    当 s=0.3, r=8, b=16:
        P ≈ 1 - (1 - 0.3^8)^16 ≈ 1 - 0.9999^16 ≈ 0.0016

时间复杂度:
    建索引:  O(n × k × |S|)  n=文档数, k=签名维度, |S|=shingle数
    单查询:  O(k + c × k)   c=候选集大小 (通常很小)
    vs 暴力的 O(n² × |S|)
"""

import hashlib
from typing import Dict, List, Set, Tuple

from datasketch import MinHash, MinHashLSH


class Deduplicator:
    """
    去重器

    结合两种去重策略:
    1. 精确去重 (MD5 hash):  O(1) 查询，适用于短文本
    2. 近似去重 (MinHash+LSH): 高效查询，适用于长文本

    数据流:
        ┌──────────┐    短文本    ┌──────────────┐
        │   文档    │──────────→  │  MD5 精确去重  │
        └──────────┘              └──────────────┘
               │
               │ 长文本
               ↓
        ┌──────────────┐
        │  MinHash LSH  │
        │  近似去重      │
        └──────────────┘

    参数说明:
        short_text_threshold: 文本长度阈值，低于此值用精确去重
        num_perm:             MinHash 签名维度 (推荐 128)
        lsh_threshold:        LSH 相似度阈值 (推荐 0.8-0.85)
    """

    def __init__(
        self,
        short_text_threshold: int = 500,
        num_perm: int = 128,
        lsh_threshold: float = 0.85
    ):
        self.short_text_threshold = short_text_threshold
        self.num_perm = num_perm
        self.lsh_threshold = lsh_threshold

        self.exact_hashes: Set[str] = set()
        self.lsh = MinHashLSH(
            threshold=lsh_threshold,
            num_perm=num_perm
        )
        self.doc_minhashes: Dict[str, MinHash] = {}

        self.stats = {
            'total_processed': 0,
            'exact_duplicates': 0,
            'approx_duplicates': 0,
            'unique': 0,
        }

    def _get_shingles(self, text: str, k: int = 5) -> Set[str]:
        """
        将文本转换为 k-gram shingles

        Shingling 是 MinHash 的第一步，将文本表示为固定长度的
        连续子串集合。

        原理:
            文本: "hello world"

            k=3 的 shingles:
            {"hel", "ell", "llo", "lo ", "o w", " wo", "wor", "orl", "rld"}

            相似文本会产生大量重叠的 shingles
            不同文本的 shingle 集合交集很小

        Args:
            text: 输入文本
            k: shingle 长度 (字符数)，推荐 3-5

        Returns:
            set: shingle 集合
        """
        text = text.lower()
        text = ' '.join(text.split())
        shingles = set()
        for i in range(len(text) - k + 1):
            shingles.add(text[i:i + k])
        return shingles

    def _compute_minhash(self, text: str) -> MinHash:
        """
        计算文本的 MinHash 签名

        算法步骤:
        1. 生成 shingle 集合
        2. 对每个置换函数 h_i，计算所有 shingle 哈希值的最小值
        3. 将所有最小值组成签名向量

        MinHash 定理保证:
            P(sig(A)[i] == sig(B)[i]) = Jaccard(A, B)

        因此:
            E[(sig(A) == sig(B) 的分量数) / k] = Jaccard(A, B)
        """
        m = MinHash(num_perm=self.num_perm)
        shingles = self._get_shingles(text)
        for s in shingles:
            m.update(s.encode('utf-8'))
        return m

    def _compute_exact_hash(self, text: str) -> str:
        """计算文本的 MD5 精确哈希"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def check(self, doc_id: str, text: str) -> Dict:
        """
        检查文档是否重复

        Args:
            doc_id: 文档唯一标识符
            text: 文档文本内容

        Returns:
            dict: {
                'is_duplicate': bool  - 是否为重复文档
                'method': str         - 'exact' | 'approximate' | 'new'
                'similar_docs': list  - 相似文档 ID (近似去重时)
                'stats': dict         - 当前统计信息
            }
        """
        self.stats['total_processed'] += 1

        if len(text) < self.short_text_threshold:
            return self._exact_check(text)
        else:
            return self._approximate_check(doc_id, text)

    def _exact_check(self, text: str) -> Dict:
        """精确去重检查 (O(1))"""
        text_hash = self._compute_exact_hash(text)

        if text_hash in self.exact_hashes:
            self.stats['exact_duplicates'] += 1
            return {
                'is_duplicate': True,
                'method': 'exact',
                'similar_docs': [],
                'stats': dict(self.stats)
            }

        self.exact_hashes.add(text_hash)
        self.stats['unique'] += 1
        return {
            'is_duplicate': False,
            'method': 'exact',
            'similar_docs': [],
            'stats': dict(self.stats)
        }

    def _approximate_check(self, doc_id: str, text: str) -> Dict:
        """近似去重检查 (MinHash + LSH)"""
        m = self._compute_minhash(text)
        candidates = self.lsh.query(m)

        if candidates:
            self.stats['approx_duplicates'] += 1
            return {
                'is_duplicate': True,
                'method': 'approximate',
                'similar_docs': candidates,
                'stats': dict(self.stats)
            }

        self.lsh.insert(doc_id, m)
        self.doc_minhashes[doc_id] = m
        self.stats['unique'] += 1
        return {
            'is_duplicate': False,
            'method': 'approximate',
            'similar_docs': [],
            'stats': dict(self.stats)
        }

    def get_stats(self) -> Dict:
        """获取去重统计"""
        total = self.stats['total_processed']
        dup_total = (
            self.stats['exact_duplicates'] +
            self.stats['approx_duplicates']
        )
        return {
            **self.stats,
            'dedup_rate': round(dup_total / total, 4) if total else 0,
            'retention_rate': round(
                self.stats['unique'] / total, 4
            ) if total else 0,
        }


if __name__ == '__main__':
    dedup = Deduplicator(short_text_threshold=80, lsh_threshold=0.6)

    test_docs = [
        ("doc1", "The quick brown fox jumps over the lazy dog."),
        ("doc2", "The quick brown fox jumps over the lazy dog."),
        ("doc3", "The quick brown fox jumps over the lazy cat."),
        ("doc4", "Machine learning is a subset of artificial intelligence. "
                 "It enables computers to learn from data without being "
                 "explicitly programmed."),
        ("doc5", "Deep learning uses neural networks with many layers "
                 "to model complex patterns in large datasets."),
    ]

    print("=" * 60)
    print("Deduplicator - Test Results")
    print("=" * 60)

    for doc_id, text in test_docs:
        result = dedup.check(doc_id, text)
        status = "DUPLICATE" if result['is_duplicate'] else "UNIQUE"
        print(f"  {doc_id}: {status} ({result['method']})")

    print("\nStats:", dedup.get_stats())