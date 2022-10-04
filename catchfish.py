import os, io, sys, json, redis, hashlib, inspect, datetime
from stockfish import Stockfish, StockfishException
import chess, chess.pgn
from pydash.strings import slugify


class Catchfish:
    """
    Convenience class for Catchfish

            .
        ":"
        ___:____     |"\/"|
    ,'        `.    \  /
    |  O        \___/  |
    ~^~^~^~^~^~^~^~^~^~^~^~^~
    “In this world, shipmates, sin that pays its way can travel freely and without a passport;
    whereas Virtue, if a pauper, is stopped at all frontiers.” Moby-Dick
    """

    def __init__(
        self,
        limit_games=0,
        stockfish_versions=[15],
        historical=True,
        log_level="info",
        threads=32,
        hash_size=1024,
        depth=20,
        multi_pv=3,
        num_nodes=["30M"],
        mode="nodes",
        engine_log_file="debug.log",
        raw_output=False,
    ):
        self._limit_games = limit_games
        self._stockfish_versions = stockfish_versions
        self._historical = historical
        self._log_level = log_level
        self._threads = threads
        self._hash = hash_size
        self._depth = depth
        self._multi_pv = multi_pv
        self._num_nodes = num_nodes
        self._mode = mode
        self._engine_log_file = engine_log_file
        self._raw_output = raw_output

        self._logger = Logger(level=self._log_level)
        self._logger.info("Initiated")
        self._logger.debug("Log level:", self._log_level)

        self.games = None
        self.evaluation = None
        self.analysis = None

    def load_games(self, path):
        self.games = Games(
            path=path,
            log_level=self._log_level,
            limit_games=self._limit_games,
        )
        self._logger.info("Games found: {}".format(len(self.games.get_games())))
        self._logger.info(
            "Invalid games found: {}".format(self.games.get_invalid_games_count())
        )

    def evaluate(self):
        """
        Evaluate a pgn file
        """

        self.evaluation = Evaluation(
            games=self.games,
            stockfish_versions=self._stockfish_versions,
            historical=self._historical,
            log_level=self._log_level,
            threads=self._threads,
            hash=self._hash,
            depth=self._depth,
            multi_pv=self._multi_pv,
            num_nodes=self._num_nodes,
            mode=self._mode,
            engine_log_file=self._engine_log_file,
            raw_output=self._raw_output,
        )
        self._logger.info("Starting evaluation")
        self.evaluation.evaluate()
        self._logger.info("Evaluation finished")

        return self.evaluation

    def analyse(self, evaluation=None, log_level=None):
        """
        Analyse an evaluation
        """
        self._logger.info("Analyse evaluation")
        self.analysis = Analysis(
            evaluation=evaluation or self.evaluation,
            log_level=log_level or self._log_level,
        )
        self._analysis_result = self.analysis.analyse()
        self._logger.info("Analysis finished")

        return self._analysis_result

    def get_evaluation_by_key(self, key):
        e = Evaluation(log_level="none")
        return json.dumps(e.get_result_by_key(key))


class Logger:
    """
    Class for pretty logging of INFO, DEBUG, ERROR, etc.
    """

    levels = ["none", "info", "error", "debug", "verbose"]

    def __init__(self, level="info"):
        self._level = level

    def info(self, *message):
        if self._levels("info"):
            self._print(message, self._level)

    def error(self, *message):
        if self._levels("error"):
            self._print(message, self._level)

    def debug(self, *message):
        if self._levels("debug"):
            self._print(message, self._level)

    def verbose(self, *message):
        if self._levels("verbose"):
            self._print(message, self._level)

    def _levels(self, level):
        return self.levels.index(level) <= self.levels.index(self._level)

    def _print(self, message, level):
        print(
            "{} | {} | {}".format(
                level.upper(), self._get_caller(), " ".join(map(str, message))
            )
        )

    def _get_caller(self):
        stack = inspect.stack()
        the_class = stack[3][0].f_locals["self"].__class__.__name__
        return the_class


class Analysis:
    """
    Class for analysing evaluated games and create aggregated statistics, like centipawnloss, wdl-changes, etc. Takes
    Evaluation result and outputs Analysis result.

    """

    def __init__(self, evaluation=None, log_level="info"):
        self._analysis = {}
        self._moves = []
        self._stockfish_variant = None
        self._evaluation = evaluation

        self._log_level = log_level
        self._logger = Logger(level=self._log_level)
        self._logger.info("Initiated")

        self._initiate_stockfish_variant()
        self._initiate_evaluation()

    def _initiate_stockfish_variant(self, stockfish_version=15, threads=32):
        if self._stockfish_variant is not None:
            self._stockfish_variant.quit()

        self._stockfish_variant = StockfishVariant(
            version=stockfish_version,
            threads=threads,
            log_level=self._log_level,
            initiate=True,
        )

    def _initiate_evaluation(self):

        # create moves by parsing PGN
        self._pgn = io.StringIO(self._evaluation["pgn"])
        self._game = Game(
            game=chess.pgn.read_game(self._pgn), log_level=self._log_level
        )
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
        self._logger.verbose("Moves:", self._moves, len(self._moves))

    def analyse(self, return_move_data=False):
        self._return_move_data = return_move_data
        return self._analyse()
        # things to analyse:
        # - √ centipawnloss per move
        # - √ centipawnloss average for whole game
        # - √ centipawnloss average for select moves (not opening, not forced, etc)
        # - √ count inaccuracies, mistakes, blunders
        # - √ mark forced moves (where only one or two moves are acceptable)
        # - √ wdl loss per move
        # - √ wdl loss average for whole game
        # - √ material on board (39/39 etc.)
        # - √ top move choices
        # - top move choices for select moves (not opening, not forced, etc)
        # - difference in engines' evaluations (special case, requires multiple inputs)
        #   - deep moves (ie. which only strong engines found)
        #   - fix engines on certain depth, and find moves which appear only at higher depth.. ie. depth-index of move
        # - historically_acccurate = if engine used was available at the time of the game
        # - ELO performance according to engine
        # - ELO performance compared to ELO of player in game
        # - mixing best moves from different engine/num_nodes
        #
        # - How deep is the position? Ie. when does the engine top move on max depth first appear? If it appears only on depth 18,
        #   that's a very deep position. If it appears already on depth 1-4, then it's not a deep position.
        # - How deep is the move that was actually made? When did this move appear (if at all) in the engine's top 1, 3, 5 moves?
        #   If a player makes a move that appears only in engine top 1, 3, 5 moves on depth 18, that's a very deep move. This is
        #   then a measaure of how deep moves the player actually makes. This is different from how similiar to engine moves the
        #   player makes, as many moves are easy/shallow, but still top engine moves.
        #
        #   [] How deep are the moves based on 1) depth, 2) selective depth, 3) nodes, in reverse order of importance.
        #
        # goal:
        # - to show all (relevant) moves in a game compared to engines on different strengths
        # - compare susmann with other players
        # - display on beautiful waterfall graph
        # - if cheating, should be outlier. if not outlier, no proof as such
        # - if cheating, might find correlation with certain engine types/strengths

    def _analyse(self):

        self._position_depths = []
        self._move_depths = []

        # per move
        for idx, move in enumerate(self._moves):
            self._analyse_move(move, idx)

        self._logger.info(
            "Position depths", self._position_depths, len(self._position_depths)
        )
        self._logger.info("Move depths", self._move_depths, len(self._move_depths))

        # per game
        self._analyse_game()

        for move in self._moves:
            move.pop("board")

        if not self._return_move_data:
            for move in self._moves:
                move.pop("evaluation")

        return json.dumps(
            {
                "info": self._game.get_info(),
                "game": self._game_analysis,
                "moves": self._moves,
            }
        )

    def _analyse_game(self):

        white_acl_all_moves = self._get_acl_all("white")
        white_acl_select_moves = self._get_acl_select(
            turn="white", ignore_first_moves=10, ignore_forced_moves=3
        )
        white_wdl_delta_all_moves = self._get_awdl_all("white")
        white_wdl_delta_select_moves = self._get_awdl_select(
            turn="white", ignore_first_moves=10, ignore_forced_moves=3
        )
        white_top_engine_moves = self._get_top_engine_moves("white")
        (
            white_inaccuracies_all_moves,
            white_mistakes_all_moves,
            white_blunders_all_moves,
        ) = self._get_inaccuracies_all("white")
        (
            white_inaccuracies_select_moves,
            white_mistakes_select_moves,
            white_blunders_select_moves,
        ) = self._get_inaccuracies_select(
            turn="white", ignore_first_moves=10, ignore_forced_moves=3
        )

        black_acl_all_moves = self._get_acl_all("black")
        black_acl_select_moves = self._get_acl_select(
            turn="black", ignore_first_moves=10, ignore_forced_moves=3
        )
        black_wdl_delta_all_moves = self._get_awdl_all("black")
        black_wdl_delta_select_moves = self._get_awdl_select(
            turn="black", ignore_first_moves=10, ignore_forced_moves=3
        )
        black_top_engine_moves = self._get_top_engine_moves("black")
        (
            black_inaccuracies_all_moves,
            black_mistakes_all_moves,
            black_blunders_all_moves,
        ) = self._get_inaccuracies_all("black")
        (
            black_inaccuracies_select_moves,
            black_mistakes_select_moves,
            black_blunders_select_moves,
        ) = self._get_inaccuracies_select(
            turn="black", ignore_first_moves=10, ignore_forced_moves=3
        )

        self._game_analysis = {
            "white": {
                "acl_all_moves": white_acl_all_moves,
                "acl_select_moves": white_acl_select_moves,
                "wdl_delta_all_moves": white_wdl_delta_all_moves,
                "wdl_delta_select_moves": white_wdl_delta_select_moves,
                "top_engine_moves": white_top_engine_moves,
                "inaccuracies_all_moves": white_inaccuracies_all_moves,
                "mistakes_all_moves": white_mistakes_all_moves,
                "blunders_all_moves": white_blunders_all_moves,
                "inaccuracies_select_moves": white_inaccuracies_select_moves,
                "mistakes_select_moves": white_mistakes_select_moves,
                "blunders_select_moves": white_blunders_select_moves,
            },
            "black": {
                "acl_all_moves": black_acl_all_moves,
                "acl_select_moves": black_acl_select_moves,
                "wdl_delta_all_moves": black_wdl_delta_all_moves,
                "wdl_delta_select_moves": black_wdl_delta_select_moves,
                "top_engine_moves": black_top_engine_moves,
                "inaccuracies_all_moves": black_inaccuracies_all_moves,
                "mistakes_all_moves": black_mistakes_all_moves,
                "blunders_all_moves": black_blunders_all_moves,
                "inaccuracies_select_moves": black_inaccuracies_select_moves,
                "mistakes_select_moves": black_mistakes_select_moves,
                "blunders_select_moves": black_blunders_select_moves,
            },
            "position_depths": self._position_depths,
            "move_depths": self._move_depths,
        }

    def _get_acl_all(self, turn):
        cpls = []
        for move in self._moves:
            if move["turn"] == turn:
                cpls.append(move["centipawn_loss"]) if move[
                    "centipawn_loss"
                ] is not None else None
        return round(sum(cpls) / len(cpls), 1) if len(cpls) > 0 else None

    def _get_acl_select(self, turn, ignore_first_moves=10, ignore_forced_moves=3):
        cpls = []
        for idx, move in enumerate(self._moves):
            if move["turn"] == turn:
                if (
                    idx >= ignore_first_moves
                    and move["legal_moves"] > ignore_forced_moves
                ):
                    cpls.append(move["centipawn_loss"]) if move[
                        "centipawn_loss"
                    ] is not None else None
        return round(sum(cpls) / len(cpls), 1) if len(cpls) > 0 else None

    def _get_awdl_all(self, turn):
        win_diffs = []
        draw_diffs = []
        lose_diffs = []
        for move in self._moves:
            if move["turn"] == turn:
                win_diffs.append(move["wdl_diff"][0]) if move[
                    "wdl_diff"
                ] is not None else None
                draw_diffs.append(move["wdl_diff"][1]) if move[
                    "wdl_diff"
                ] is not None else None
                lose_diffs.append(move["wdl_diff"][2]) if move[
                    "wdl_diff"
                ] is not None else None
        return (
            round(sum(win_diffs) / len(win_diffs), 1) if len(win_diffs) > 0 else None,
            round(sum(draw_diffs) / len(draw_diffs), 1)
            if len(draw_diffs) > 0
            else None,
            round(sum(lose_diffs) / len(lose_diffs), 1)
            if len(lose_diffs) > 0
            else None,
        )

    def _get_awdl_select(self, turn, ignore_first_moves=10, ignore_forced_moves=3):
        win_diffs = []
        draw_diffs = []
        lose_diffs = []
        for idx, move in enumerate(self._moves):
            if move["turn"] == turn:
                if (
                    idx >= ignore_first_moves
                    and move["legal_moves"] > ignore_forced_moves
                ):
                    win_diffs.append(move["wdl_diff"][0]) if move[
                        "wdl_diff"
                    ] is not None else None
                    draw_diffs.append(move["wdl_diff"][1]) if move[
                        "wdl_diff"
                    ] is not None else None
                    lose_diffs.append(move["wdl_diff"][2]) if move[
                        "wdl_diff"
                    ] is not None else None
        return (
            round(sum(win_diffs) / len(win_diffs), 1) if len(win_diffs) > 0 else None,
            round(sum(draw_diffs) / len(draw_diffs), 1)
            if len(draw_diffs) > 0
            else None,
            round(sum(lose_diffs) / len(lose_diffs), 1)
            if len(lose_diffs) > 0
            else None,
        )

    def _get_top_engine_moves(self, turn):
        top_engine_moves = {}
        for move in self._moves:
            if move["turn"] == turn:
                if "top_engine_move" in move and move["top_engine_move"] is not None:
                    if move["top_engine_move"] in top_engine_moves:
                        top_engine_moves[move["top_engine_move"]] += 1
                    else:
                        top_engine_moves[move["top_engine_move"]] = 1
        return top_engine_moves

    def _get_inaccuracies_all(self, turn):
        inaccuracies = 0
        mistakes = 0
        blunders = 0
        for move in self._moves:
            if move["turn"] == turn:
                if move["centipawn_loss"] is not None and move["centipawn_loss"] >= 50:
                    inaccuracies += 1
                if move["centipawn_loss"] is not None and move["centipawn_loss"] >= 100:
                    mistakes += 1
                if move["centipawn_loss"] is not None and move["centipawn_loss"] >= 300:
                    blunders += 1
        return inaccuracies, mistakes, blunders

    def _get_inaccuracies_select(
        self, turn, ignore_first_moves=10, ignore_forced_moves=3
    ):
        inaccuracies = 0
        mistakes = 0
        blunders = 0
        for idx, move in enumerate(self._moves):
            if move["turn"] == turn:
                if (
                    idx >= ignore_first_moves
                    and move["legal_moves"] > ignore_forced_moves
                ):
                    if (
                        move["centipawn_loss"] is not None
                        and move["centipawn_loss"] >= 50
                    ):
                        inaccuracies += 1
                    if (
                        move["centipawn_loss"] is not None
                        and move["centipawn_loss"] >= 100
                    ):
                        mistakes += 1
                    if (
                        move["centipawn_loss"] is not None
                        and move["centipawn_loss"] >= 300
                    ):
                        blunders += 1
        return inaccuracies, mistakes, blunders

    def _analyse_move(self, move, idx):
        centipawn_loss = self._get_centipawn_loss(move, idx)
        self._logger.debug("Centipawn loss: ", centipawn_loss)

        wdl_diff = self._get_wdl_diff(move, idx)
        self._logger.debug("WDL loss: ", wdl_diff)

        top_engine_move = self._get_top_move(move)
        self._logger.debug("Top move index: ", top_engine_move)

        legal_moves_count = self._get_num_legal_moves(move)
        self._logger.debug("Legal moves count: ", legal_moves_count)

        material = self._get_material(move)
        self._logger.debug("Material: ", material)

        depth_of_position = self._get_depth_of_position(move)
        self._logger.info("Depth of position: ", depth_of_position)

        depth_of_move = self._get_depth_of_move(move)
        self._logger.info("Depth of move: ", depth_of_move)

        self._moves[idx].update(
            {
                "centipawn_loss": centipawn_loss,
                "wdl_diff": wdl_diff,
                "top_engine_move": top_engine_move,
                "legal_moves": legal_moves_count,
                "material": material,
            }
        )

    def _get_depth_of_move(self, move, depth_cutoff=3):
        move_made = move["move"]
        depths = self._sort_depths_of_evaluation(move)
        depth_of_move = self._drill_down_move(depths, move_made, depth_cutoff)
        self._move_depths.append(depth_of_move["depth"] if depth_of_move else 0)
        return depth_of_move

    def _drill_down_move(self, depths, move_made, depth_cutoff=3):
        jd = []
        made_move_was_top_move_in_these_depths = []

        for depth in depths:
            d = depths[depth][0]
            if d["Move"] == move_made:
                jd.append(int(d["Depth"]))
                made_move_was_top_move_in_these_depths.append(
                    {
                        "nodes": int(d["Nodes"]),
                        "depth": int(d["Depth"]),
                        "time": int(d["Time"]),
                        "move": d["Move"],
                    }
                )

        for n in range(1, depth_cutoff + 1):
            jd.remove(n) if n in jd else None

        move_depth = jd[0] if len(jd) > 0 else None

        if move_depth is None:
            return None

        num_p_d = len(jd)
        agreement = (num_p_d) / (jd[-1] - jd[0] + 1)
        depth_of_move = {
            "depth": move_depth,
            "depths": jd,
            "agreement": agreement,
        }

        return depth_of_move

    def _get_depth_of_position(self, move, depth_cutoff=3):
        depths = self._sort_depths_of_evaluation(move)
        deepest_evaluation = depths[max(depths, key=int)]
        deepest_move = deepest_evaluation[0]["Move"]  # eg "e2e4"
        depth_of_position = self._drill_down_move(depths, deepest_move, depth_cutoff)
        self._position_depths.append(depth_of_position["depth"])
        return depth_of_position

    def _sort_depths_of_evaluation(self, move):
        depths = {}
        for e in move["evaluation"]:
            if "Nodes" in e:
                d = e["Nodes"]
                if d in depths:
                    depths[d].append(e)
                else:
                    depths[d] = [e]
        return depths

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

    def _get_top_move(self, move):
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

        wdl_player = (
            player_move["WDL"]
            if player_move is not None and "WDL" in player_move
            else None
        )
        wdl_best = (
            best_move["WDL"] if best_move is not None and "WDL" in best_move else None
        )
        wdl_diff = self._calc_wdl_diff(wdl_player, wdl_best)
        self._logger.debug(" WDL diffs: ", wdl_diff, wdl_player, wdl_best)

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
                and move["evaluation"][0]["Centipawn"] is not None
                and self._moves[idx + 1]["evaluation"][0]["Centipawn"] is not None
                else None
            )

        if cpl is None:
            # eg. if evaluation is mate in n moves
            pass

        return abs(cpl) if cpl is not None else None

    def _get_move_made(self, move):
        self._logger.debug("Got a move: ", move)
        fen = move["position"]
        pgn = io.StringIO(self._game["moves"])
        self._game_moves = chess.pgn.read_game(pgn)
        self._logger.debug("Got game moves: ", self._game_moves)


class RedisStore:
    """
    Class for Redis store, used by Evaluation to store and retrieve results. Faster and safer than writing to file.
    """

    def __init__(
        self, host="localhost", port=6379, db=1, connect=True, log_level="info"
    ):
        self._host = host
        self._port = port
        self._db = db

        self._log_level = log_level
        self._logger = Logger(level=self._log_level)
        self._logger.info("Initiated")

        self.connect() if connect else None

    def connect(self):
        self._logger.info("Connecting to Redis", self._host, self._port, self._db)
        self._store = redis.Redis(host=self._host, port=self._port, db=self._db)

    def get(self, key):
        self._logger.debug("Getting key", key)
        value = self._store.get(key)
        if value:
            return self.loads(value)

    def loads(self, value):
        try:
            return json.loads(value)
        except:
            return value

    def set(self, key, value):
        self._logger.debug("Setting key", key)
        return self._store.set(key, self.dumps(value))

    def dumps(self, value):
        try:
            return json.dumps(value)
        except:
            return value


class Evaluation:
    """
    Class for making an evaluation of whole games. Takes Games, returns statistics.

    """

    def __init__(
        self,
        games=None,
        stockfish_versions=[9, 10, 11, 12, 13, 14, 15],
        historical=True,
        log_level="info",
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
        raw_output=False,
    ):
        self._stockfish_variant = None
        self._evaluations = []
        self._game_results_store_keys = []
        self._results = []
        self._restarts = 0
        self._crashes = 0
        self._game = None
        self._games = games
        self._stockfish_versions = stockfish_versions
        self._historical = historical
        self._threads = threads
        self._hash = hash
        self._depth = depth
        self._multi_pv = multi_pv
        self._num_nodes = num_nodes
        self._mode = mode
        self._include_info = include_info
        self._engine_log_file = engine_log_file
        self._raw_output = raw_output

        self._log_level = log_level
        self._logger = Logger(level=self._log_level)
        self._logger.info("Initiated")

        self._store = RedisStore(
            host=redis_host, port=redis_port, db=redis_db, log_level=self._log_level
        )

    def evaluate(self):

        self._logger.info(
            "Running evaluation matrix with",
            self._stockfish_versions,
            "Stockfish versions and",
            self._num_nodes,
            "number of nodes.",
        )

        self._evaluate()

    def _evaluate(self):
        # for each stockfish
        # for each num_nodes
        # for each game
        # for each fen
        for stockfish_version in self._stockfish_versions:
            self._stockfish_version = stockfish_version
            self._logger.info("Using Stockfish version", stockfish_version)
            self._initiate_stockfish_variant(stockfish_version)
            for num_nodes in self._num_nodes:
                self._current_num_nodes = num_nodes
                self._logger.debug("Setting", self._current_num_nodes, "nodes.")

                for game in self.get_games():
                    self._game = game

                    self._logger.debug(
                        "Evaluating game",
                        game.get_info_string(),
                    )

                    for position in game.get_positions():
                        self._fen = position
                        self._evaluate_position()

                    self._save_game_evaluation()

        return self._game_results_store_keys

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
            log_level=self._log_level,
            include_info=self._include_info,
            debug_log_file=self._engine_log_file,
            initiate=True,
            raw_output=self._raw_output,
        )

    def _evaluate_position(self):
        self._stockfish_variant.set_num_nodes(self._current_num_nodes)
        self._stockfish_variant.set_position(self._fen)

        try:
            exisiting_evaluation = self._get_position_evaluation()
            if exisiting_evaluation:
                self._logger.debug(
                    "Evaluation already exists for position",
                    self._fen,
                    "with num_nodes",
                    self._current_num_nodes,
                )
                self._set_position_evaluation(exisiting_evaluation)
                return
            else:
                evaluation = self._stockfish_variant.evaluate_position()
                self._set_position_evaluation(evaluation)
        except StockfishException as sfe:
            self._logger.info("Stockfish has crashed. Fixing...")
            self._logger.debug(
                "Stockfish crash info:",
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
            "raw_output": self._raw_output,
        }

    def _restart_stockfish_after_crash(self):
        self._logger.info("Restarting Stockfish")

        if self._restarts < 200:
            self._restarts += 1
            self._initiate_stockfish_variant(self._stockfish_version)
            self._evaluate_position()
        else:
            self._logger.info("Too many restarts. Quitting!")
            sys.exit(1)

    def _save_game_evaluation(self):
        self._logger.debug("Saving game evaluation.")
        result = {
            "info": self._game.get_info(),
            "description": self._game.get_info_string(),
            "evaluation": self._evaluations,
            "engine": self._stockfish_variant.get_long_version(),
            "num_nodes": self._num_nodes,
            "pgn": self._game.get_pgn(headers=True),
        }
        key = self._write_to_store("game", result)
        if key:
            self._game_results_store_keys.append(
                {"description": result["description"], "key": key}
            )

        self._evaluations = []

    def _write_to_store(self, prefix, data):
        store_key = (
            prefix + ":" + hashlib.md5(json.dumps(data).encode("utf-8")).hexdigest()
        )
        self._logger.debug("Store key:", store_key)
        if self._store.set(store_key, data):
            self._logger.info(
                "Game stored:",
                {"description": data["description"], "key": store_key},
            )
            return store_key
        else:
            self._logger.debug("Store key not saved:", store_key)

    def _read_from_store(self, store_key):
        self._logger.debug("Store key:", store_key)
        result = self._store.get(store_key)
        if result:
            self._logger.debug("Store key found:", store_key)
            return result
        else:
            self._logger.debug("Store key not found:", store_key)
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

    def _get_position_evaluation(self):
        return self._store.get(self._gen_pos_eval_key())

    def _set_position_evaluation(self, evaluation):
        self._evaluations.append(
            {
                "evaluation": evaluation,
                "position": self._fen,
            }
        )
        self._store.set(self._gen_pos_eval_key(), evaluation)

    def _gen_pos_eval_key(self):
        return (
            "position:"
            + hashlib.md5(
                json.dumps([self._get_settings(), self._fen]).encode("utf-8")
            ).hexdigest()
        )

    def get_results(self):
        self._results = []
        for item in self._game_results_store_keys:
            result = self._read_from_store(item["key"])
            if result:
                self._results.append(result)
        return self._results

    def get_result_keys(self):
        return self._game_results_store_keys

    def get_result_by_key(self, key):
        return self._read_from_store(key)


class Game:
    """
    Class for a single game. Created by Games class by passing a chess Game.
    """

    def __init__(self, game=None, validate_fen=False, log_level="info"):
        self._headers = {}
        self._info = {}
        self._valid = False
        self._game = game
        self._validate_fen = validate_fen

        self._log_level = log_level
        self._logger = Logger(level=self._log_level)
        self._logger.debug("Initiated")

        self._validate_game()

        if not self._valid:
            return None

        self._set_info()

        self._logger.debug("Game created: \n", game)

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
            + self.get_header("Result")
            + " "
            + self.get_header("Date")
            + " "
            + self.get_header("Event")
            + " "
            + self.get_header("Round")
            + " "
            + self.get_header("PlyCount")
        )

    def get_positions(self):
        self._positions = []
        game = self._game
        self._logger.debug("Reading positions in game.")
        while True:
            try:
                self._positions.append(self._get_fen(game))
                game = game.next() if game.next() is not None else game
            except ValueError as ve:
                self._logger.debug("Error:", ve)
                continue

            if game.next() is None:
                self._logger.debug("Reached end of game.")
                break
        return self._positions

    def get_moves(self):
        self._logger.debug("Reading moves in game.")
        game = self._game
        while not game.is_end():
            board = game.board()
            move = board.peek()
            self._logger.debug("Fullmove number:", board.fullmove_number)
            self._logger.debug("Peeked move:", move)
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
                self._logger.debug(
                    "Not a regular chess game, probably 960. Skipping!",
                )
                self._valid = False
            else:
                # todo: check all positions
                if self._validate_fen == True:
                    valid = self._stockfish.is_fen_valid(fen)
                    if valid is False:
                        self._logger.debug("FEN is not valid. Skipping!")
                        self._valid = False
                    self._logger.debug("FEN is valid.")
                    self._valid = True
                else:
                    self._valid = True
        except Exception as e:
            self._logger.debug(
                "Failed to validate game. Skipping! | Error was: ",
                e,
            )
            self._valid = False

    def is_valid(self):
        return self._valid

    def _get_fen(self, game):
        try:
            return game.board().fen()
        except Exception as e:
            self._logger.debug("Error", e)
            return None

    def _parse_date(self, date):
        try:
            return datetime.datetime.strptime(date, "%Y.%m.%d")  # YY.MM.DD
        except:
            pass
        try:
            return datetime.datetime.strptime(date, "%Y-%m-%d")  # YY-MM-DD
        except:
            self._logger.debug("Could not parse date.", date)
            return date


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
        log_level="info",
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
        self._validate_fen = validate_fen
        self._limit_games = limit_games if limit_games > 0 else 1000000

        self._log_level = log_level
        self._logger = Logger(level=self._log_level)
        self._logger.info("Initiated")

        self._logger.debug("Games created.")

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
        self._logger.debug("Ingesting games from PGN")
        while True and not self._limit_reached():
            try:
                game = chess.pgn.read_game(self._pgn)  # could be many games
                self.ingest_game(game)
            except KeyboardInterrupt:
                # quit
                self._logger.error("Keyboard interrupt. Quitting!")
                sys.exit()
            except Exception as e:
                self._logger.debug("Failed to ingest game. Skipping!", e)
                continue
            if game is None:
                break
        self._logger.info("Ingested", len(self._games), "games.")

    def ingest_game(self, game):
        g = Game(game=game, log_level=self._log_level)
        if g.is_valid():
            self._games.append(g)
        else:
            self._invalid_games += 1

    def get_games(self):
        return self._games

    def get_invalid_games_count(self):
        return self._invalid_games

    def get_valid_games_count(self):
        return len(self._games)

    def parse_date(self, date):
        try:
            return datetime.datetime.strptime(date, "%Y.%m.%d")  # YY.MM.DD
        except:
            pass
        try:
            return datetime.datetime.strptime(date, "%Y-%m-%d")  # YY-MM-DD
        except:
            self._logger.debug("Could not parse date.", date)
            return False


class StockfishVariant:
    """
    Class for running Stockfish variants.
    """

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
        log_level="info",
        debug_log_file=None,
        include_info=True,
        raw_output=False,
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
        self._debug_log_file = debug_log_file
        self._include_info = include_info
        self._raw_output = raw_output

        self._log_level = log_level
        self._logger = Logger(level=self._log_level)

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
        self._logger.info("Stockfish version", self._version, "initiated.")
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

    def set_position(self, fen, refresh=True):
        self._logger.debug("Setting position", fen)
        return self._stockfish.set_fen_position(fen, refresh)

    def is_fen_valid(self, fen):
        self._logger.debug("Validating FEN.")
        return self._stockfish.is_fen_valid(fen)

    def set_num_nodes(self, num_nodes):
        self._logger.debug("Setting num nodes", num_nodes)
        num_nodes = num_nodes.replace("M", "000000")
        num_nodes = num_nodes.replace("m", "000000")
        num_nodes = num_nodes.replace("K", "000")
        num_nodes = num_nodes.replace("k", "000")
        self._num_nodes = (
            int(num_nodes) if int(num_nodes) > 100000 else 100000
        )  # 100k minimum

    def evaluate_position(self):
        self._logger.debug("Evaluating position.")

        if self._raw_output:
            top_moves = self._stockfish.get_raw_lines(
                multi_pv=self._multi_pv, num_nodes=self._num_nodes
            )
        else:
            top_moves = self._stockfish.get_top_moves(
                num_top_moves=self._multi_pv,
                include_info=True,
                num_nodes=self._num_nodes,
            )

        self._logger.debug("Result of evaluation:", top_moves)
        return top_moves

    def quit(self):
        self._logger.debug("Quitting.")
        self._stockfish.send_quit_command()
