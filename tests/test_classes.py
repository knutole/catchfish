import pytest
from timeit import default_timer
import time
import os

from catchfish import StockfishVariant, Games, Game


class TestStockfishVariant:
    """
    Test StockfishVariant class
    """

    @pytest.fixture
    def stockfish_variant(self):
        return StockfishVariant()

    def test_get_version(self, stockfish_variant):
        version = stockfish_variant.get_version()
        assert version is 15

    def test_get_parameters(self, stockfish_variant):
        parameters = stockfish_variant.get_parameters()
        assert parameters is not None


class TestGames:
    """
    Test Games class
    """

    @pytest.fixture
    def games(self):
        return Games()

    def say_hello(self, games):
        assert games.say_hello() is "hello"

    def test_add_pgn(self, games):
        file = os.path.join(os.path.dirname(__file__), "test.pgn")
        games.read_file(file)
        assert len(games._games) > 0
