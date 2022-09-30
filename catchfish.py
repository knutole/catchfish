from re import S
from stockfish import Stockfish, StockfishException
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
import os, io
import pydash
import hashlib


class Logger:
    """
    Class for pretty logging of INFO, DEBUG, ERROR, etc.
    """

    def __init__(self, level="info"):
        self._level = level


class Analysis:
    """
    Class for analysing evaluated games and create aggregated statistics, like centipawnloss, wdl-changes, etc. Takes
    Evaluation result and outputs Analysis result.
    """

    def __init__(self, evaluation=None, debug_level=4):
        self._analysis = {}
        self._moves = []
        self._stockfish_variant = None
        self._evaluation = evaluation
        self._debug_level = debug_level

        self._initiate_stockfish_variant()
        self._initiate_evaluation()

    def _initiate_stockfish_variant(self, stockfish_version=15, threads=32):
        if self._stockfish_variant is not None:
            self._stockfish_variant.quit()

        self._stockfish_variant = StockfishVariant(
            version=stockfish_version,
            threads=threads,
            debug_level=self._debug_level,
            initiate=True,
        )

    def analyse(self):
        self._analyse()
        pass
        # things to analyse:
        # - √ centipawnloss per move
        # - centipawnloss average for whole game
        # - centipawnloss average for select moves (not opening, not forced, etc)
        # - count inaccuracies, mistakes, blunders
        # - √ mark forced moves (where only one or two moves are acceptable)
        # - √ wdl loss per move
        # - wdl loss average for whole game
        # - √ material on board (39/39 etc.)
        # - √ top move choices
        # - top move choices for select moves (not opening, not forced, etc)
        # - difference in engines' evaluations (special case, requires multiple inputs)
        #   - deep moves (ie. which only strong engines found)
        #   - fix engines on certain depth, and find moves which appear only at higher depth.. ie. depth-index of move
        # - historically_acccurate = if engine used was available at the time of the game
        # - ELO performance according to engine
        # - ELO performance compared to ELO of player in game
        #
        # goal:
        # - to show all (relevant) moves in a game compared to engines on different strengths
        # - compare susmann with other players
        # - display on beautiful waterfall graph
        # - if cheating, should be outlier. if not outlier, no proof as such
        # - if cheating, might find correlation with certain engine types/strengths

    def _analyse(self):

        # per move
        for idx, move in enumerate(self._moves):
            self._analyse_move(move, idx)

        # per game
        self.print(4, "Analysis | Debug | Moves: ", self._moves)

    def _analyse_move(self, move, idx):
        centipawn_loss = self._get_centipawn_loss(move, idx)
        self.print(5, "Analysis | Debug | Centipawn loss: ", centipawn_loss)

        wdl_diff = self._get_wdl_diff(move, idx)
        self.print(5, "Analysis | Debug | WDL loss: ", wdl_diff)

        top_engine_move = self._get_top_moves(
            move
        )  # 0 means not found, otherwise 1 to multi_pv
        self.print(5, "Analysis | Debug | Top move index: ", top_engine_move)

        legal_moves_count = self._get_num_legal_moves(move)
        self.print(5, "Analysis | Debug | Legal moves count: ", legal_moves_count)

        material = self._get_material(move)
        self.print(5, "Analysis | Debug | Material: ", material)

        self._moves[idx].update(
            {
                "centipawn_loss": centipawn_loss,
                "wdl_diff": wdl_diff,
                "top_engine_move": top_engine_move,
                "legal_moves": legal_moves_count,
                "material": material,
            }
        )

    def _get_material(self, move):
        board = move["board"]
        piece_map = board.piece_map()
        wm = 0
        bm = 0
        for piece in piece_map:
            v = self._get_piece_value(piece_map[piece].piece_type)
            if piece_map[piece].color == chess.WHITE:
                wm += v
            else:
                bm += v
        return [wm, bm]

    def _get_piece_value(self, piece):
        if piece == 1:  # pawn
            return 1
        elif piece == 2:  # knight
            return 3
        elif piece == 3:  # bishop
            return 3
        elif piece == 4:  # rook
            return 5
        elif piece == 5:  # queen
            return 9
        elif piece == 6:  # king
            return 0
        else:
            return 0

    def _get_num_legal_moves(self, move):
        return move["board"].legal_moves.count()

    def _get_top_moves(self, move):
        move_made = move["move"]
        top_move_index = next(
            (
                index
                for (index, d) in enumerate(move["evaluation"])
                if d["Move"] == move_made
            ),
            None,
        )
        return top_move_index + 1 if top_move_index is not None else 0

    def _get_wdl_diff(self, move, idx):
        move_made = move["move"]
        was_top_move = next(
            (item for item in move["evaluation"] if item["Move"] == move_made), None
        )
        best_move = move["evaluation"][0]

        if was_top_move is not None:
            player_move = was_top_move
        else:
            player_move = (
                self._moves[idx + 1]["evaluation"][0]
                if len(self._moves) > idx + 1
                else None
            )

        wdl_player = player_move["WDL"] if player_move is not None else None
        wdl_best = best_move["WDL"] if best_move is not None else None
        wdl_diff = self._calc_wdl_diff(wdl_player, wdl_best)
        return wdl_diff

    def _calc_wdl_diff(self, wdl_a, wdl_b):
        wdl_a = wdl_a.split(" ") if wdl_a is not None else None
        wdl_b = wdl_b.split(" ") if wdl_b is not None else None
        if wdl_a is None or wdl_b is None:
            return None

        w = int(wdl_b[0]) - int(wdl_a[0])
        d = int(wdl_b[1]) - int(wdl_a[1])
        l = int(wdl_b[2]) - int(wdl_a[2])
        return [w, d, l]

    def _get_centipawn_loss(self, move, idx):
        move_made = move["move"]
        top_move = next(
            (item for item in move["evaluation"] if item["Move"] == move_made), None
        )
        if top_move is not None:
            cpl = (
                top_move["Centipawn"] - move["evaluation"][0]["Centipawn"]
                if move["evaluation"][0]["Centipawn"] is not None
                else None
            )
        else:
            cpl = (
                self._moves[idx + 1]["evaluation"][0]["Centipawn"]
                - move["evaluation"][0]["Centipawn"]
                if len(self._moves) > idx + 1
                else None
            )

        if cpl is None:
            # eg. if evaluation is mate in n moves
            pass

        return abs(cpl) if cpl is not None else None

    def _initiate_evaluation(self):

        # create moves by parsing PGN
        self._pgn = io.StringIO(self._evaluation["pgn"])
        self._game = Game(game=chess.pgn.read_game(self._pgn))
        self._boards = self._game.get_boards()

        moves = []

        for i, board in enumerate(self._boards):
            moves.append(
                {
                    "board": board,
                    "fullmove_number": board.fullmove_number,
                    "ply": board.ply() + 1,
                    "turn": "white" if board.turn else "black",
                    "move": self._boards[i + 1].peek().uci()
                    if len(self._boards) > i + 1
                    else None,
                    "is_check": board.is_check(),
                    "is_checkmate": board.is_checkmate(),
                    "is_stalemate": board.is_stalemate(),
                    "is_insufficient_material": board.is_insufficient_material(),
                }
            )

        for idx, e_move in enumerate(self._evaluation["evaluation"]):
            moves[idx].update(e_move)

        self._moves = moves
        self.print(5, "\nAnalysis | Debug | Moves:", self._moves, len(self._moves))

    def _get_move_made(self, move):
        self.print(5, "Analysis | Debug | Got a move: ", move)
        fen = move["position"]
        pgn = io.StringIO(self._game["moves"])
        self._game_moves = chess.pgn.read_game(pgn)
        self.print(5, "Analysis | Debug | Got game moves: ", self._game_moves)

    def print(self, level, *argv):
        if self._debug_level >= level:
            print(*argv)


class RedisStore:
    """
    Class for Redis store, used by Evaluation to store and retrieve results. Faster and safer than writing to file.
    """

    def __init__(self, host="localhost", port=6379, db=1, connect=True, debug_level=4):
        self._host = host
        self._port = port
        self._db = db
        self._debug_level = debug_level

        self.connect() if connect else None

    def connect(self):
        self.print(
            4, "Redis | Debug | Connecting to Redis", self._host, self._port, self._db
        )
        self._redis = redis.Redis(host=self._host, port=self._port, db=self._db)

    def get(self, key):
        self.print(4, "Redis | Debug | Getting key", key)
        value = self._redis.get(key)
        if value:
            return self.loads(value)

    def loads(self, value):
        try:
            return json.loads(value)
        except:
            return value

    def set(self, key, value):
        self.print(4, "Redis | Debug | Setting key", key)
        return self._redis.set(key, self.dumps(value))

    def dumps(self, value):
        try:
            return json.dumps(value)
        except:
            return value

    def print(self, level, *argv):
        if self._debug_level >= level:
            print(*argv)


class Evaluation:
    """
    Class for making an evaluation of whole games. Takes Games, returns statistics.
    """

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
        redis_host="localhost",
        redis_port=6379,
        redis_db=1,
        engine_log_file=None,
    ):
        self._stockfish_variant = None
        self._evaluations = []
        self._game_results_redis_keys = []
        self._results = []
        self._restarts = 0
        self._crashes = 0
        self._game = None
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
        self._engine_log_file = engine_log_file
        self._redis = RedisStore(host=redis_host, port=redis_port, db=redis_db)

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
            self._stockfish_version = stockfish_version
            self.print(
                2, "Evaluation | Debug | Using Stockfish version", stockfish_version
            )
            self._initiate_stockfish_variant(stockfish_version)
            for num_nodes in self._num_nodes:
                self._current_num_nodes = num_nodes
                self.print(
                    2, "Evaluation | Info | Setting", self._current_num_nodes, "nodes."
                )

                for game in self.get_games():
                    self._game = game
                    self.print(
                        3,
                        "Evaluation | Debug | Evaluating game",
                        game.get_info(as_json=True),
                    )

                    for position in game.get_positions():
                        self._fen = position
                        self._evaluate_position()

                    self._save_game_evaluation()

        return self._game_results_redis_keys

    def get_games(self):
        return self._games.get_games()

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
            debug_log_file=self._engine_log_file,
            initiate=True,
        )

    def _evaluate_position(self):
        self._stockfish_variant.set_num_nodes(self._current_num_nodes)
        self._stockfish_variant.set_position(self._fen)

        try:
            evaluation = self._stockfish_variant.evaluate_position()
            self._save_position_evaluation(evaluation)
        except StockfishException as sfe:
            self.print(
                2,
                "Evaluation | Error | Stockfish has crashed.",
                sfe,
                self._get_settings(),
                self._fen,
            )
            self._crashes += 1
            self._restart_stockfish_after_crash()

    def _get_settings(self):
        return {
            "threads": self._threads,
            "hash": self._hash,
            "depth": self._depth,
            "multi_pv": self._multi_pv,
            "num_nodes": self._num_nodes,
            "mode": self._mode,
            "include_info": self._include_info,
            "version": self._stockfish_version,
        }

    def _restart_stockfish_after_crash(self):
        self.print(3, "Evaluation | Debug | Restarting Stockfish")

        if self._restarts < 10:
            self._restarts += 1
            self._initiate_stockfish_variant(self._stockfish_version)
            self._evaluate_position()
        else:
            self.print(2, "Evaluation | Error | Too many restarts. Quitting!")
            sys.exit(1)

    def _save_game_evaluation(self):
        self.print(4, "Evaluation | Debug | Saving game evaluation.")
        result = {
            "info": self._game.get_info(),
            "evaluation": self._evaluations,
            "engine": self._stockfish_variant.get_long_version(),
            "num_nodes": self._num_nodes,
            "pgn": self._game.get_pgn(headers=True),
        }
        self._write(result)
        self._evaluations = []

    def _write(self, result):
        self._write_to_redis(result)

    def _write_to_redis(self, result):
        redis_key = hashlib.md5(json.dumps(result).encode("utf-8")).hexdigest()
        self.print(5, "Evaluation | Verbose | Redis key:", redis_key)
        ok = self._redis.set(redis_key, result)
        if ok:
            self.print(5, "Evaluation | Verbose | Redis key saved:", redis_key)
            self._game_results_redis_keys.append(redis_key)
        else:
            self.print(5, "Evaluation | Error | Redis key not saved:", redis_key)

    def _read_from_redis(self, redis_key):
        self.print(5, "Evaluation | Verbose | Redis key:", redis_key)
        result = self._redis.get(redis_key)
        if result:
            self.print(5, "Evaluation | Verbose | Redis key found:", redis_key)
            return result
        else:
            self.print(5, "Evaluation | Error | Redis key not found:", redis_key)
            return None

    def _write_to_file(self, result):
        file = (
            "/home/ubuntu/catchfish/data/evaluations/"
            + slugify(self._game.get_info())
            + "_"
            + str(self._num_nodes)
            + "_"
            + str(self._stockfish_variant.get_version())
            + ".json"
        )
        os.makedirs(os.path.dirname(file), exist_ok=True)
        with open(file, "w") as gf:
            gf.write(json.dumps(result))
            gf.close()

    def _save_position_evaluation(self, evaluation):
        self.print(5, "Evaluation | Verbose | Saving evaluation:", evaluation)
        self._evaluations.append(
            {
                "evaluation": evaluation,
                "position": self._fen,
            }
        )

    def get_results(self):
        self._results = []
        for redis_key in self._game_results_redis_keys:
            result = self._read_from_redis(redis_key)
            if result:
                self._results.append(result)
        return self._results

    def get_result_keys(self):
        return self._game_results_redis_keys

    def get_result_by_key(self, key):
        return self._read_from_redis(key)

    def print(self, level, *argv):
        if self._debug_level >= level:
            print(*argv)


class Game:
    """
    Class for a single game. Created by Games class by passing a chess Game.
    """

    def __init__(self, game=None, validate_fen=False, debug_level=4):
        self._headers = {}
        self._info = {}
        self._valid = False
        self._game = game
        self._validate_fen = validate_fen
        self._debug_level = debug_level

        self._validate_game()

        if not self._valid:
            return None

        self._set_info()

        self.print(5, "Game | Debug | Game created: \n", game)

    def get_game(self):
        return self._game

    def get_pgn(self, headers=False, variations=False, comments=False):
        exporter = chess.pgn.StringExporter(
            headers=headers, variations=variations, comments=comments
        )
        return self._game.game().accept(exporter)

    def _set_info(self):
        self._info["white"] = self.get_header("White")
        self._info["black"] = self.get_header("Black")
        self._info["date"] = self.get_header("Date")
        self._info["result"] = self.get_header("Result")
        self._info["event"] = self.get_header("Event")
        self._info["round"] = self.get_header("Round")
        self._info["white_elo"] = self.get_header("WhiteElo")
        self._info["black_elo"] = self.get_header("BlackElo")
        self._info["eco"] = self.get_header("ECO")
        self._info["ply"] = self.get_header("PlyCount")
        self._info["moves"] = self.get_pgn()

    def get_headers(self):
        return self._game.headers

    def get_header(self, header):
        try:
            return self._game.headers[header]
        except:
            return None

    def get_white_player(self):
        return self.get_header("White")

    def get_white_playah(self):
        return self._headers["white"]

    def get_info(self, as_json=False):
        if as_json:
            return json.dumps(self._info)
        else:
            return self._info

    def get_info_string(self):
        return (
            self.get_header("White")
            + " vs "
            + self.get_header("Black")
            + " "
            + self.get_header("Date")
            + " "
            + self.get_header("Result")
            + " "
            + self.get_header("Event")
        )

    def get_positions(self):
        self._positions = []
        game = self._game
        self.print(4, "Game | Debug | Reading positions in game.")
        while True:
            try:
                self._positions.append(self._get_fen(game))
                game = game.next() if game.next() is not None else game
            except ValueError as ve:
                self.print(4, "Game | Error |", ve)
                continue

            if game.next() is None:
                self.print(5, "Game | Debug | Reached end of game.")
                break
        return self._positions

    def get_moves(self):
        self.print(4, "Game | Debug | Reading moves in game.")
        game = self._game
        while not game.is_end():
            board = game.board()
            move = board.peek()
            self.print(4, "Game | Debug | Fullmove number:", board.fullmove_number)
            self.print(4, "Game | Debug | Peeked move:", move)
            game = game.next()
        self._move_stack = board.move_stack
        return board.move_stack

    def get_boards(self):
        boards = []
        game = self._game
        while not game.is_end():
            board = game.board()
            boards.append(board)
            game = game.next()
        return boards

    def _validate_game(self, game=None):
        game = game if game else self._game
        try:
            fen = game.board().fen()
            if fen != chess.STARTING_FEN:
                self.print(
                    3,
                    "Game | Warning | Not a regular chess game, probably 960. Skipping!",
                )
                self._valid = False
            else:
                # todo: check all positions
                if self._validate_fen == True:
                    valid = self._stockfish.is_fen_valid(fen)
                    if valid is False:
                        self.print(3, "Game | Warning | FEN is not valid. Skipping!")
                        self._valid = False
                    self.print(4, "Game | Debug | FEN is valid.")
                    self._valid = True
                else:
                    self._valid = True
        except Exception as e:
            self.print(
                3,
                "Game | Warning | Failed to validate game. Skipping! | Error was: ",
                e,
            )
            self._valid = False

    def is_valid(self):
        return self._valid

    def _get_fen(self, game):
        try:
            return game.board().fen()
        except Exception as e:
            self.print(4, "Game | Error |", e)
            return None

    def _parse_date(self, date):
        try:
            return datetime.datetime.strptime(date, "%Y.%m.%d")  # YY.MM.DD
        except:
            pass
        try:
            return datetime.datetime.strptime(date, "%Y-%m-%d")  # YY-MM-DD
        except:
            self.print(2, "Games | Error | Could not parse date.", date)
            return date

    def print(self, level, *argv):
        if self._debug_level >= level:
            print(*argv)


class Games:
    """
    Class for reading one or several games from a PGN string, and creating a Game for each game in the PGN string.
    """

    def __init__(
        self,
        path=None,
        pgn=None,
        allow_960=False,
        stockfish_variant=None,
        debug_level=4,
        validate_fen=True,
        limit_games=0,
    ):
        self._games = []
        self._invalid_games = 0
        self._headers = {}
        self._pgn = pgn
        self._path = path
        self._allow_960 = allow_960
        self._stockfish = stockfish_variant or StockfishVariant(initiate=True)
        self._debug_level = debug_level
        self._validate_fen = validate_fen
        self._limit_games = limit_games if limit_games > 0 else 1000000

        self.print(4, "Games | Debug | Games created.")

        if pgn is not None:
            self.add_pgn()

        if path is not None:
            self.read_file(path)

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

    def _limit_reached(self):
        return len(self._games) >= self._limit_games

    def ingest_pgn(self):
        self.print(3, "Games | Debug | Ingesting games from PGN")
        while True and not self._limit_reached():
            try:
                game = chess.pgn.read_game(self._pgn)  # could be many games
                self.ingest_game(game)
            except KeyboardInterrupt:
                # quit
                self.print(1, "Games | Critical | Keyboard interrupt. Quitting!")
                sys.exit()
            except Exception as e:
                self.print(3, "Games | Error | Failed to ingest game. Skipping!", e)
                continue
            if game is None:
                break

    def ingest_game(self, game):
        g = Game(game=game)
        if g.is_valid():
            self._games.append(g)
        else:
            self._invalid_games += 1

    def get_games(self):
        return self._games

    def get_invalid_games(self):
        return self._invalid_games

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

    # todo: symlinks
    _binaries_folder = "/home/ubuntu/catchfish/stockfish"

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
        debug_log_file=None,
        include_info=True,
    ):
        self._initiated = False
        self._version = version
        self._depth = depth
        self._multi_pv = multi_pv
        self._num_nodes = num_nodes
        self._threads = threads
        self._hash = hash
        self._mode = mode
        self._binaries_folder = binaries_folder or self._binaries_folder
        self._debug_level = debug_level
        self._debug_log_file = debug_log_file
        self._include_info = include_info

        self.set_parameters()

        if initiate == True:
            self.initiate()

    def initiate(self):
        self._stockfish = Stockfish(
            path=self.get_path(),
            depth=self._depth,
            parameters=self.get_parameters(),
        )
        self._initiated = True
        self.print(
            2, "Stockfish | Info | Stockfish version", self._version, "initiated."
        )
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
        self._parameters["Debug Log File"] = self._debug_log_file or ""

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
        self._num_nodes = (
            int(num_nodes) if int(num_nodes) > 100000 else 100000
        )  # 100k minimum

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
