"""
模块 1: 网页清洗 (HTML Cleaner)
==============================
将 Common Crawl 原始 HTML 转换为干净的纯文本

核心原理:
    - DOM 树解析: BeautifulSoup 将 HTML 解析为树结构
    - 噪声移除: 删除 script, style, nav, footer 等非内容标签
    - 正文提取: 优先提取 <article>, <main> 等语义化区域
    - 编码处理: 检测并过滤乱码内容

输入: 原始 HTML 字符串
输出: 干净的纯文本
"""

import re
from pathlib import Path
from typing import Dict, Optional

from bs4 import BeautifulSoup, Comment


class HTMLCleaner:
    """
    HTML 清洗器

    将原始 HTML 文档清洗为干净文本，包含以下步骤:
    1. 解析 HTML DOM 树
    2. 移除噪声标签 (脚本、样式、广告、导航等)
    3. 移除 HTML 注释
    4. 提取主要内容区域
    5. 清理空白和冗余字符
    6. 乱码检测

    使用示例:
        >>> cleaner = HTMLCleaner(min_text_length=50)
        >>> result = cleaner.clean("<html><body><p>Hello World</p></body></html>")
        >>> print(result['text'])
    """

    NOISE_TAGS = [
        'script',        # JavaScript
        'style',         # CSS 样式
        'nav',           # 导航栏
        'footer',        # 页脚
        'header',        # 页头
        'aside',         # 侧边栏
        'iframe',        # 嵌入框架
        'noscript',      # 无脚本替代
        'svg',           # 矢量图形
        'canvas',        # 画布元素
        'button',        # 按钮
        'input',         # 输入框
        'form',          # 表单
        'select',        # 下拉框
        'textarea',      # 文本域
        'img',           # 图片(alt 文本价值有限)
        'video',         # 视频
        'audio',         # 音频
        'embed',         # 嵌入对象
        'object',        # 对象
    ]

    MAIN_CONTENT_SELECTORS = [
        'article',
        'main',
        '[role="main"]',
        '.content',
        '.post-content',
        '.entry-content',
        '.article-content',
        '#content',
        '#main',
        '#article',
        '.post',
        '.article',
    ]

    def __init__(self, min_text_length: int = 50):
        """
        初始化 HTML 清洗器

        Args:
            min_text_length: 最小文本长度阈值 (字符数)
                           低于此值的文档将视为无意义内容
        """
        self.min_text_length = min_text_length

    def _parse_html(self, html_content: str) -> BeautifulSoup:
        """解析 HTML 字符串为 BeautifulSoup DOM 树"""
        return BeautifulSoup(html_content, 'lxml')

    def _remove_noise_tags(self, soup: BeautifulSoup) -> BeautifulSoup:
        """
        移除噪声标签

        对每个噪声标签调用 decompose() 彻底删除节点。
        decompose() 会将标签及其所有子内容从 DOM 树中移除，
        并清除所有引用，使其可被垃圾回收。
        """
        for tag_name in self.NOISE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        return soup

    def _remove_comments(self, soup: BeautifulSoup) -> BeautifulSoup:
        """移除所有 HTML 注释"""
        for comment in soup.find_all(
            string=lambda text: isinstance(text, Comment)
        ):
            comment.extract()
        return soup

    def _extract_main_content(self, soup: BeautifulSoup) -> BeautifulSoup:
        """
        提取主要内容区域

        策略:
        1. 尝试匹配语义化内容标签 (article, main 等)
        2. 遇到多个匹配时，选择文本最长的 (通常是主内容)
        3. 回退到 <body> 标签
        4. 最后回退到整个文档
        """
        best = None
        best_len = 0

        for selector in self.MAIN_CONTENT_SELECTORS:
            elements = soup.select(selector)
            for el in elements:
                text_len = len(el.get_text())
                if text_len > best_len:
                    best_len = text_len
                    best = el

        if best:
            return best
        return soup.find('body') or soup

    def _clean_text(self, text: str) -> str:
        """
        清理提取出的文本

        处理步骤:
        1. 移除残留的 HTML 标签
        2. 合并多个连续空白为单个空格
        3. 按段落清理和筛选
        4. 用双换行连接段落，保留结构
        """
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)

        paragraphs = []
        for line in text.split('\n'):
            line = line.strip()
            if len(line) > 5:
                paragraphs.append(line)

        if not paragraphs:
            words = text.split()
            chunks = []
            chunk = []
            for word in words:
                chunk.append(word)
                if len(' '.join(chunk)) > 200:
                    chunks.append(' '.join(chunk))
                    chunk = []
            if chunk:
                chunks.append(' '.join(chunk))
            paragraphs = chunks

        return '\n\n'.join(paragraphs)

    def _detect_garbage(self, text: str) -> bool:
        """
        检测文本是否为乱码

        判断标准:
        1. 可打印字符比例 < 80% → 可能是二进制乱码
        2. 字母/空格/常用标点比例 < 50% → 不是自然语言
        """
        if not text:
            return True

        printable_count = sum(
            1 for c in text
            if c.isprintable() or c.isspace()
        )
        if printable_count / len(text) < 0.8:
            return True

        natural_char_count = sum(
            1 for c in text
            if c.isalpha() or c.isspace() or c in '.,!?;:"()-\''
        )
        if natural_char_count / len(text) < 0.5:
            return True

        return False

    def clean(self, html_content: str) -> Dict:
        """
        清洗 HTML 文档

        Args:
            html_content: 原始 HTML 字符串

        Returns:
            dict: {
                'success': bool    - 是否成功
                'text': str|None   - 清洗后的文本
                'error': str|None  - 错误信息 (如有)
            }
        """
        try:
            soup = self._parse_html(html_content)
            soup = self._remove_noise_tags(soup)
            soup = self._remove_comments(soup)
            main_content = self._extract_main_content(soup)
            text = main_content.get_text(separator='\n')
            text = self._clean_text(text)

            if len(text) < self.min_text_length:
                return {
                    'success': False,
                    'text': None,
                    'error': f'Text too short: {len(text)} chars'
                }

            if self._detect_garbage(text):
                return {
                    'success': False,
                    'text': None,
                    'error': 'Garbage / mojibake detected'
                }

            return {
                'success': True,
                'text': text,
                'error': None
            }

        except Exception as e:
            return {
                'success': False,
                'text': None,
                'error': str(e)
            }

    def clean_file(self, file_path: str) -> Dict:
        """清洗单个 HTML 文件"""
        path = Path(file_path)
        if not path.exists():
            return {
                'success': False,
                'text': None,
                'error': f'File not found: {file_path}'
            }
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
        return self.clean(html)


if __name__ == '__main__':
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title><script>var x=1;</script><style>body{}</style></head>
    <body>
        <nav>Home | About | Contact</nav>
        <article>
            <h1>Introduction to Machine Learning</h1>
            <p>Machine learning is a subset of artificial intelligence (AI)
            that provides systems the ability to automatically learn and improve
            from experience without being explicitly programmed.</p>
            <p>Machine learning focuses on the development of computer programs
            that can access data and use it to learn for themselves.</p>
        </article>
        <footer>&copy; 2024 All Rights Reserved</footer>
    </body>
    </html>
    """

    cleaner = HTMLCleaner(min_text_length=30)
    result = cleaner.clean(sample_html)

    print("=" * 60)
    print("HTML Cleaner - Test Result")
    print("=" * 60)
    print(f"Success: {result['success']}")
    if result['success']:
        print(f"Text length: {len(result['text'])} chars")
        print(f"Text preview:\n{result['text'][:300]}...")
    else:
        print(f"Error: {result['error']}")