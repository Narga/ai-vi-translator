import pytest
import re
from webui.routes.projects import (
    _compile_portable_regex,
    _portable_replacement_adapter,
    _apply_portable_regex
)

def test_compile_portable_regex():
    # literal normal
    p1 = _compile_portable_regex("heLlo.?", "normal")
    assert p1.pattern == r"heLlo\.\?"
    assert p1.flags & re.IGNORECASE
    
    # literal case-sensitive
    p2 = _compile_portable_regex("heLlo", "case-sensitive")
    assert p2.pattern == "heLlo"
    assert not (p2.flags & re.IGNORECASE)
    
    # regex
    p3 = _compile_portable_regex(r"^# .*\n", "regex")
    assert p3.pattern == r"^# .*\n"
    assert p3.flags & re.MULTILINE
    
    # CRLF -> LF normalization in compilation
    p4 = _compile_portable_regex("a\r\nb", "regex")
    assert p4.pattern == "a\nb"

def test_portable_replacement_adapter():
    # $1 to \g<1>
    assert _portable_replacement_adapter("Hello $1") == r"Hello \g<1>"
    assert _portable_replacement_adapter("$1$2") == r"\g<1>\g<2>"
    # Escaped \$1 should be ignored
    assert _portable_replacement_adapter(r"Price \$10 and $1") == r"Price \$10 and \g<1>"

def test_apply_portable_regex_count():
    content = "Hello\r\nHello World\nhello"
    p = _compile_portable_regex("hello", "normal")
    count, new_c = _apply_portable_regex(content, p)
    assert count == 3
    assert new_c == "Hello\nHello World\nhello"
    
    # regex with group (ensure finditer handles group count correctly)
    p_regex = _compile_portable_regex(r"(Hello)", "regex")
    count, _ = _apply_portable_regex(content, p_regex)
    assert count == 2

def test_apply_portable_regex_replace():
    content = "## Chương 1\r\n\r\n### Chương 2"
    p = _compile_portable_regex(r"^#+\s+(Chương\s+\d+)", "regex")
    
    count, new_c = _apply_portable_regex(content, p, "## $1")
    assert count == 2
    assert new_c == "## Chương 1\n\n## Chương 2"
    
def test_apply_portable_regex_zero_width():
    content = "abc"
    p = _compile_portable_regex(r"^", "regex")
    count, new_c = _apply_portable_regex(content, p, "X")
    assert count == 1
    assert new_c == "Xabc"
