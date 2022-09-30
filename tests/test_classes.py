import pytest
from timeit import default_timer
import time
import os

from catchfish import StockfishVariant, Games, Game


class TestStockfishVariant:
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
    @pytest.fixture
    def games(self):
        return Games()

    def say_hello(self, games):
        print("saing hlello")
        assert games.say_hello() is "hello"

    def test_add_pgn(self, games):
        file = os.path.join(os.path.dirname(__file__), "test.pgn")
        # pgn = open(file)
        games.read_file(file)
        print("got some games:", len(games._games))
        assert len(games._games) > 0
