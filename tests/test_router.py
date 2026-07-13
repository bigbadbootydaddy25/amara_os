from app.foreman.router import parse_response


def test_parse_response_reads_well_formed_json():
    raw = '{"text": "Full answer.", "speakable_text": "Short answer."}'
    text, speakable = parse_response(raw)
    assert text == "Full answer."
    assert speakable == "Short answer."


def test_parse_response_falls_back_for_non_json_output():
    raw = "This model ignored the instructions. It just wrote prose. More prose here."
    text, speakable = parse_response(raw)
    assert text == raw
    assert speakable == "This model ignored the instructions."
