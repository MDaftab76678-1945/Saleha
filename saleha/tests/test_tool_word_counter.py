import pytest
from saleha.tools.word_counter import WordCounterTool

@pytest.fixture
def word_counter_tool():
    return WordCounterTool()

def test_word_counter_execute_normal(word_counter_tool):
    result = word_counter_tool.execute(text='Hello world')
    assert result.success is True
    assert result.data == {'word_count': 2}

def test_word_counter_execute_empty_text(word_counter_tool):
    result = word_counter_tool.execute(text='')
    assert result.success is True
    assert result.data == {'word_count': 0}

def test_word_counter_execute_single_word(word_counter_tool):
    result = word_counter_tool.execute(text='Hello')
    assert result.success is True
    assert result.data == {'word_count': 1}

def test_word_counter_execute_multiple_spaces(word_counter_tool):
    result = word_counter_tool.execute(text='   Hello world   ')
    assert result.success is True
    assert result.data == {'word_count': 2}