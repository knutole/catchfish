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


class PositionEvaluation:
    """
    Class for making an evaluation of a position. Takes a GamePosition and a StockfishVariant, returns stats.
    """

    pass


class Evaluation:
    """
    Class for making an evaluation of whole games. Takes Games, returns statistics.
    """

    _stockfish_variant = None

    def __init__(
        self,
        games=None,
        stockfish_versions=[9, 10, 11, 12, 13, 14, 15],
        historical=True,
        debug_level=4,
        threads=196,
        hash=4096,
        depth=20,
        multi_pv=3,
        num_nodes=["1M", "10M"],
        mode="nodes",
        include_info=True,
    ):
        self._games = games
        self._stockfish_versions = stockfish_versions
        self._historical = historical
        self._debug_level = debug_level
        self._threads = threads
        self._hash = hash
        self._depth = depth
        self._multi_pv = multi_pv
        self._num_nodes = num_nodes
        self._mode = mode
        self._include_info = include_info

    def evaluate(self):
        self.print(
            3,
            "Evaluation | Info | Running evaluation matrix with",
            self._stockfish_versions,
            "Stockfish versions and",
            self._num_nodes,
            "number of nodes.",
        )

        self.print(4, "Evaluation | Debug | Games:", self._games.get_games())

        self._evaluate()

    def _evaluate(self):
        # for each stockfish
        # for each num_nodes
        # for each game
        # for each fen
        for stockfish_version in self._stockfish_versions:
            self.print(
                3, "Evaluation | Debug | Using Stockfish version", stockfish_version
            )
            self._initiate_stockfish_variant(stockfish_version)
            for num_nodes in self._num_nodes:
                self._num_nodes = num_nodes
                self.print(
                    3, "Evaluation | Debug | Searching", self._num_nodes, "nodes."
                )

                for game in self.get_games():
                    self.print(
                        3, "Evaluation | Debug | Evaluating game", game.get_info()
                    )

                    for position in game.get_positions():
                        self._fen = position
                        self._evaluate_position()

    def get_games(self):
        return self._games.get_games()

    def _evaluate_position(self):
        self._stockfish_variant.set_num_nodes(self._num_nodes)
        self._stockfish_variant.set_position(self._fen)
        evaluation = self._stockfish_variant.evaluate_position()
        self._save_evaluation(evaluation)

    def _initiate_stockfish_variant(self, stockfish_version):
        if self._stockfish_variant is not None:
            self._stockfish_variant.quit()

        self._stockfish_variant = StockfishVariant(
            version=stockfish_version,
            threads=self._threads,
            hash=self._hash,
            depth=self._depth,
            multi_pv=self._multi_pv,
            mode=self._mode,
            debug_level=self._debug_level,
            include_info=self._include_info,
            initiate=True,
        )

    def _save_evaluation(self, evaluation):
        self.print(3, "Evaluation | Debug | Saving evaluation:", evaluation)
        pass

    def print(self, level, *argv):
        if self._debug_level >= level:
            print(*argv)


class GamePosition:
    """
    Class for Game positions.
    """

    pass


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

    def get_info(self):
        return (
            self._headers["white"]
            + " vs "
            + self._headers["black"]
            + " "
            + self._headers["date"]
            + " "
            + self._headers["result"]
            + " "
            + self._headers["event"]
        )

    def get_positions(self):
        self._positions = []
        game = self._game
        while True:
            try:
                game = game.next() if game.next() is not None else game
                self._positions.append(self._get_fen(game))
            except ValueError as ve:
                self.print(4, "Evaluation | Error |", ve)
                continue

            if game.next() is None:
                self.print(4, "Evaluation | Debug | No more positions.")
                break
        return self._positions

    def _get_fen(self, game):
        try:
            return game.board().fen()
        except Exception as e:
            self.print(4, "Evaluation | Error |", e)
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
                self.print(3, "Games | Error | Failed to ingest game. Skipping!")
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
                self.print(
                    3,
                    "Games | Warning | Not a regular chess game, probably 960. Skipping!",
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
        include_info=True,
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
        self._include_info = include_info

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

    def set_position(self, fen, refresh=False):
        self.print(4, "StockfishVariant | Debug | Setting position", fen)
        return self._stockfish.set_fen_position(fen, refresh)

    def is_fen_valid(self, fen):
        self.print(4, "StockfishVariant | Debug | Validating FEN.")
        return self._stockfish.is_fen_valid(fen)

    def set_num_nodes(self, num_nodes):
        self.print(4, "StockfishVariant | Debug | Setting num nodes", num_nodes)
        num_nodes = num_nodes.replace("M", "000000")
        num_nodes = num_nodes.replace("m", "000000")
        num_nodes = num_nodes.replace("K", "000")
        num_nodes = num_nodes.replace("k", "000")
        self._num_nodes = int(num_nodes)

    def evaluate_position(self):
        self.print(4, "StockfishVariant | Debug | Evaluating position.")
        top_moves = self._stockfish.get_top_moves(
            num_top_moves=self._multi_pv, include_info=True, num_nodes=self._num_nodes
        )
        self.print(5, "StockfishVariant | Debug! | Result of evaluation:", top_moves)
        return top_moves

    def quit(self):
        self.print(4, "StockfishVariant | Debug | Quitting.")
        self._stockfish.send_quit_command()

    def print(self, level, *argv):
        if self._debug_level >= level:
            print(*argv)


if __name__ == "__main__":

    # stockfish = StockfishVariant(version=13)
    # print(stockfish.get_release_date())
    # print(stockfish.get_nnue())
    # print(stockfish._version)
    # # test

    # file = os.path.join(os.path.dirname(__file__), "tests/" "test.pgn")
    # games = Games(path=file, validate_fen=True)

    # import cProfile, pstats
    # profiler = cProfile.Profile()
    # profiler.enable()
    #################################################
    # # games = Games(path=file, validate_fen=True)
    #################################################
    # profiler.disable()
    # stats = pstats.Stats(profiler).sort_stats("cumtime")
    # stats.print_stats()

    # print(games.get_games()[0]._game.headers)
    # print(type(games.get_games()[0]._game.headers))
    # game = games.get_games()[0]
    # print("game", game)
    # print(game.get_headers())
    # print(game.get_header("Event"))
    # print(game._headers)

    # example
    #
    # - got a path to pgn
    # - want to evaluate all games
    # - with a matrix of SF versions and depths/nodes
    # - return results of evaluation
    #

    file = os.path.join(os.path.dirname(__file__), "tests/" "test.pgn")
    games = Games(path=file)
    evaluation = Evaluation(
        games=games,
        stockfish_versions=[15],
        historical=True,
        debug_level=4,
        threads=196,
        hash=4096,
        depth=20,
        multi_pv=5,
        num_nodes=["10M"],
        mode="nodes",
    )

    evaluation.evaluate()
