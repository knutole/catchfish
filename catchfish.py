from re import S
from stockfish import Stockfish
import chess
import chess.pgn
import time
from dateutil.parser import parse
import datetime
import redis
import sys
import json
from pydash.strings import slugify
from pydash.arrays import reverse
import pprint
import os
import pydash


class Game:
    """
    Class for a single game. Created by Games class by passing a chess Game.
    """

    _headers = {}

    def __init__(self, game=None, debug_level=4):
        self._game = game
        self._debug_level = debug_level

        self.set_headers()

    def get_game(self):
        return self._game

    def set_headers(self):
        for h in self._game.headers:
            self._headers[h.lower()] = self._game.headers[h]

    def get_headers(self):
        return self._game.headers

    def get_header(self, header):
        try:
            return self._game.headers[header]
        except:
            return None

    def print(self, level, *argv):
        if self._debug_level >= level:
            print(*argv)


class Games:
    """
    Class for reading one or several games from a PGN string, and creating a Game for each game in the PGN string.
    """

    _games = []
    _invalid_games = 0

    def __init__(
        self,
        path=None,
        pgn=None,
        allow_960=False,
        stockfish_variant=None,
        debug_level=4,
        validate_fen=True,
    ):
        self._pgn = pgn
        self._path = path
        self._allow_960 = allow_960
        self._stockfish = stockfish_variant or StockfishVariant(initiate=True)
        self._debug_level = debug_level
        self._validate_fen = validate_fen

        if pgn is not None:
            self.add_pgn()

        if path is not None:
            self.read_file(path)

    def read_file(self, path=None):
        self._path = path or self._path
        pgn = open(self._path)
        self.add_pgn(pgn)

    def say_hello(self):
        return "hello"

    def add_pgn(self, pgn):
        self._pgn = pgn
        self.ingest_pgn()

    def ingest_pgn(self):
        while True:
            try:
                game = chess.pgn.read_game(self._pgn)  # could be many games
                self.ingest_game(game)
            except:
                print("Games | Error | Failed to ingest game. Skipping!")
                continue
            if game is None:
                break

    def ingest_game(self, game):
        if self.validate_game(game) is not False:
            # healthy game
            self._games.append(Game(game=game))
        else:
            self._invalid_games += 1

    def get_games(self):
        return self._games

    def validate_game(self, game):
        try:
            fen = game.board().fen()
            if fen != chess.STARTING_FEN:
                print(
                    "Games | Warning | Not a regular chess game, probably 960. Skipping!"
                )
                return False
            else:
                if self._validate_fen == True:
                    valid = self._stockfish.is_fen_valid(fen)
                    if valid is False:
                        self.print(3, "Games | Warning | FEN is not valid. Skipping!")
                        return False
                    self.print(4, "Games | Debug | FEN is valid.")
                    return game
                else:
                    return game
        except Exception as e:
            self.print(
                3,
                "Games | Warning | Failed to validate game. Skipping! | Error was: ",
                e,
            )
            return False

    def parse_date(self, date):
        try:
            return datetime.datetime.strptime(date, "%Y.%m.%d")  # YY.MM.DD
        except:
            pass
        try:
            return datetime.datetime.strptime(date, "%Y-%m-%d")  # YY-MM-DD
        except:
            self.print(2, "Games | Error | Could not parse date.", date)
            return False

    def print(self, level, *argv):
        if self._debug_level >= level:
            print(*argv)


class StockfishVariant:

    _versions = [
        {"version": 9, "release_date": "2018-02-04", "nnue": False},
        {"version": 10, "release_date": "2018-12-01", "nnue": False},
        {"version": 11, "release_date": "2020-01-15", "nnue": False},
        {"version": 12, "release_date": "2020-09-02", "nnue": True},
        {"version": 13, "release_date": "2021-02-13", "nnue": True},
        {"version": 14, "release_date": "2021-07-02", "nnue": True},
        {"version": 15, "release_date": "2022-04-18", "nnue": True},
    ]

    _binaries_folder = "/home/ubuntu/catchfish/stockfish"

    _initiated = False

    _default_parameters = {
        "Debug Log File": "",
        "Contempt": 0,
        "Min Split Depth": 0,
        "Threads": 1,
        "Ponder": "false",
        "Hash": 16,
        "MultiPV": 1,
        "Skill Level": 20,
        "Move Overhead": 10,
        "Minimum Thinking Time": 1,
        "Slow Mover": 100,
        "UCI_Chess960": "false",
        "UCI_LimitStrength": "false",
        "UCI_Elo": 2850,
    }

    def __init__(
        self,
        version=15,
        depth=20,
        multi_pv=5,
        num_nodes=100000000,
        threads=196,
        hash=4096,
        mode="nodes",
        binaries_folder=None,
        initiate=False,
        debug_level=4,
    ):
        self._version = version
        self._depth = depth
        self._multi_pv = multi_pv
        self._num_nodes = num_nodes
        self._threads = threads
        self._hash = hash
        self._mode = mode
        self._binaries_folder = binaries_folder or self._binaries_folder
        self._debug_level = debug_level

        self.set_parameters()

        if initiate == True:
            self.initiate()

    def initiate(self):
        stockfish = Stockfish(
            path=self.get_path(),
            depth=self._depth,
            parameters=self.get_parameters(),
        )
        self._stockfish = stockfish
        self._initiated = True
        return self._stockfish

    def get_version(self):
        return self._version

    def get_depth(self):
        return self._depth

    def get_mpv(self):
        return self._mpv

    def get_num_nodes(self):
        return self._num_nodes

    def get_path(self):
        return (
            self._binaries_folder
            + "/stockfish-"
            + str(self._version)
            + "/stockfish-"
            + str(self._version)
        )

    def get_parameters(self):
        return self._parameters

    def set_parameters(self):
        self._parameters = self._default_parameters
        self._parameters["Threads"] = self._threads
        self._parameters["Hash"] = self._hash
        self._parameters["MultiPV"] = self._multi_pv

    def get_release_date(self):
        return self.get_long_version()["release_date"]

    def get_long_version(self):
        return [cdict for cdict in self._versions if cdict["version"] == self._version][
            0
        ]

    def get_nnue(self):
        return self.get_long_version()["nnue"]

    def is_fen_valid(self, fen):
        self.print(4, "StockfishVariant | Debug | Validating FEN.")
        return self._stockfish.is_fen_valid(fen)

    def print(self, level, *argv):
        if self._debug_level >= level:
            print(*argv)


if __name__ == "__main__":

    stockfish = StockfishVariant(version=13)
    print(stockfish.get_release_date())
    print(stockfish.get_nnue())
    print(stockfish._version)
    # test

    file = os.path.join(os.path.dirname(__file__), "tests/" "test.pgn")
    games = Games(path=file, validate_fen=True)

    # import cProfile, pstats
    # profiler = cProfile.Profile()
    # profiler.enable()
    #################################################
    # # games = Games(path=file, validate_fen=True)
    #################################################
    # profiler.disable()
    # stats = pstats.Stats(profiler).sort_stats("cumtime")
    # stats.print_stats()

    print(games.get_games()[0]._game.headers)
    print(type(games.get_games()[0]._game.headers))
    game = games.get_games()[0]
    print("game", game)
    print(game.get_headers())
    print(game.get_header("Event"))
    print(game._headers)
