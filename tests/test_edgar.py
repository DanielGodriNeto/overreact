from overreact.edgar import clean, is_hard

RAW = """<SEC-DOCUMENT>header
<DOCUMENT>
<TYPE>8-K
<TEXT><html><p>FORM 8-K cover page boilerplate</p><p>Item 2.02 Results of Operations &amp; Condition.</p>
<p>See exhibit.</p></html></TEXT>
</DOCUMENT>
<DOCUMENT>
<TYPE>EX-99.1
<TEXT><p>Record revenue of $10M.</p></TEXT>
</DOCUMENT>
<DOCUMENT>
<TYPE>GRAPHIC
<TEXT>begin 644 logo.jpg binarygarbage</TEXT>
</DOCUMENT>"""


def test_clean_keeps_8k_and_press_release_only():
    text = clean(RAW)
    assert text.startswith("Item 2.02 Results of Operations & Condition.")
    assert "Record revenue of $10M." in text
    assert "binarygarbage" not in text and "<p>" not in text


def test_hard_forms():
    assert is_hard("8-K") and is_hard("424B5") and is_hard("10-Q")
    assert not is_hard("4") and not is_hard("SC 13G")
