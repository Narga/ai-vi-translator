from core.chunker import split_text


def test_empty_and_whitespace():
    assert split_text("") == []
    assert split_text("   \n\n  ") == []


def test_short_text():
    text = "Đoạn văn ngắn."
    assert split_text(text, max_chars=1000) == [text]


def test_split_at_double_newline():
    p1 = "Đoạn 1.\n\n" * 50
    p2 = "Đoạn 2.\n\n" * 50
    chunks = split_text(p1 + p2, max_chars=len(p1) + 100)
    assert len(chunks) >= 2


def test_split_without_spaces():
    text = "A" * 1000
    chunks = split_text(text, max_chars=600)
    assert len(chunks) == 2


def test_no_content_loss():
    text = ("Câu mở đầu. " * 200 + "\n\n" + "Đoạn hai! " * 200).strip()
    chunks = split_text(text, max_chars=2000)
    # Mọi câu nguồn phải còn nguyên trong các chunk (quy ước whitespace chuẩn hóa)
    joined = " ".join(" ".join(c.split()) for c in chunks)
    for sentence in ("Câu mở đầu.", "Đoạn hai!"):
        assert sentence in joined
