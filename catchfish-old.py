from stockfish154 import Stockfish
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
import hashlib
import os
import pydash

prettyPrint = pprint.PrettyPrinter(indent=4).pprint


def parseDate(date):
    try:
        gameDate = datetime.datetime.strptime(date, "%Y.%m.%d")
        return gameDate
    except:
        pass
    try:
        gameDate = datetime.datetime.strptime(date, "%Y-%m-%d")
        return gameDate
    except:
        return False


def getTopMoves(fen=None, stockfish=None, num_nodes=100000000):
    tm = None

    # check previous evaluation of FEN
    key = (
        "top_moves_"
        + str(ENGINE_MPV_LINES)
        + ":nodes_"
        + str(ENGINE_NODES)
        + ":"
        + ENGINE_NAME
        + "_"
        + str(ENGINE_VERSION)
        + ":"
        + fen
    )
    history = redis.get(key)
    if history is not None and DISABLE_CACHE is not True:
        tm = json.loads(history)
        print(".", end="", flush=True)
    else:

        # get top five moves
        tic = time.perf_counter()
        tm = stockfish.get_top_moves(
            ENGINE_MPV_LINES, include_info=True, num_nodes=num_nodes
        )
        toc = time.perf_counter()
        if DEBUG_LEVEL >= 3:
            print(f"Calculated the top moves in {toc - tic:0.4f} seconds")

        # save to redis
        redis.set(key, json.dumps(tm))

    return tm


def getMoveMade(g):
    try:
        node = g.next()
        if node is not None:
            return node.move
        else:
            return False
    except:
        return False


def getPieceMoved(move_made, sf):
    if move_made is False or None:
        return None
    square = sf.get_what_is_on_square(chess.square_name(move_made.from_square))
    if square is None:
        return None

    return square.name


def getWDLStats(top_moves):
    if len(top_moves):
        top = top_moves[0]
        if "WDL" in top:
            return top["WDL"]
    return None


def getCentipawnLoss(current_move, previous_move):
    try:

        # check if previous_move was first move, if so, it's 0 cpl
        if (
            previous_move["move_made"]
            == previous_move["engine"]["top_moves"][0]["Move"]
        ):
            return 0
        # get current eval of position (ie. if playing best move)
        current_evaluation = current_move["engine"]["top_moves"][0][
            "Centipawn"
        ]  # eg. 450 (+4.5)

        # get previous evaluation of position
        previous_evaluation = previous_move["engine"]["top_moves"][0][
            "Centipawn"
        ]  # eg. 350 (+3.5)

        previous_move_cpl = abs(current_evaluation - previous_evaluation)
        return previous_move_cpl
    except Exception as e:
        print("getCentipawnLoss error")
        print(e)
        return None


def getStats(moves):
    white_cpls = []
    black_cpls = []
    top_moves_white = dict.fromkeys(map(int, range(ENGINE_MPV_LINES + 1)), 0)
    top_moves_black = dict.fromkeys(map(int, range(ENGINE_MPV_LINES + 1)), 0)
    top_moves_white.pop(0)
    top_moves_black.pop(0)

    for m in moves:
        if m["white_to_move"] == True:

            try:
                # count centipawn losses
                if m["engine"]["centipawnLoss"] is not None:
                    white_cpls.append(m["engine"]["centipawnLoss"])

                # count top moves
                for i, tm in enumerate(m["engine"]["top_moves"], start=1):
                    if m["move_made"] == tm["Move"]:
                        top_moves_white[i] += 1
            except Exception as e:
                print("E1 with white ", str(e))
                print(m)
                pass

        else:
            try:
                # count centipawn losses
                if m["engine"]["centipawnLoss"] is not None:
                    black_cpls.append(m["engine"]["centipawnLoss"])

                # count top moves
                for i, tm in enumerate(m["engine"]["top_moves"], start=1):
                    if m["move_made"] == tm["Move"]:
                        top_moves_black[i] += 1
            except Exception as e:

                print("E2 with black", str(e))
                print(m)
                pass

    acl_white = sum(white_cpls) / len(white_cpls) if len(white_cpls) else None
    acl_black = sum(black_cpls) / len(black_cpls) if len(black_cpls) else None

    s = {
        "acl_white": acl_white,
        "acl_black": acl_black,
        "top_moves_white": top_moves_white,
        "top_moves_black": top_moves_black,
    }
    return s


def parseCleanGames(pgn):

    games = []
    while True:

        # read PGN
        try:
            game = chess.pgn.read_game(pgn)
        except:
            continue
        if game is None:
            break  # end of file

        # get date of game
        try:
            gameDate = parseDate(game.headers["Date"])
        except ValueError as ve:
            continue

        # only use normal variant
        try:
            # next move
            fen = game.board().fen()
            if fen != chess.STARTING_FEN:
                print("Not a regular chess game, probably 960. Skipping!")
                continue
        except:
            continue

        # use these games
        games.append(game)

    return games


def evaluateGames(file):

    pgn = open(file)

    # choose clean games
    games = reverse(parseCleanGames(pgn))

    print("Found", len(games), "games")

    # only evaluate last 100 games
    games = games[-100:]

    count = 0

    # iterate games
    for g in games:

        # debug info
        count += 1
        if DEBUG_LEVEL >= 1:
            print("\n--------------------------")
            print("Game", count, "/", len(games))
            for h in g.headers:
                print(h, g.headers[h])
            print("\nNodes:", ENGINE_NODES)
            print("\nEngine:", ENGINE_NAME, "v", ENGINE_VERSION)
            print("\n--------------------------")

        for sf in get_stockfish_versions():
            for num_nodes in get_num_nodes():

                # create stockfish instance
                stockfish = create_stockfish_instance(version=sf["version"])

                # run evaluation
                evaluateGame(g, stockfish=stockfish, num_nodes=num_nodes)


def get_num_nodes():
    return ["10000000", "50000000", "100000000", "200000000"]  # 10M, 50M, 100M, 200M


def evaluateGame(g, stockfish=None, num_nodes=None):
    gtic = time.perf_counter()

    print("Evaluating game with", stockfish)
    headers = g.headers

    # defaults
    previous_move = None
    previous_best_move = None
    centipawnLoss = None

    # reset board
    stockfish.set_fen_position(chess.STARTING_FEN)

    moves = []
    while True:

        try:
            # next move
            g = g.next() if g.next() is not None else g
        except ValueError as ve:
            continue

        if g.next() is None:
            print("No more moves")
            moves.append(previous_move)
            break

        # get FEN of position
        fen = g.board().fen()

        # set position on board
        stockfish.set_fen_position(fen, False)

        # get top moves
        top_moves = getTopMoves(fen=fen, stockfish=stockfish, num_nodes=num_nodes)

        if DEBUG_LEVEL >= 4:
            prettyPrint(top_moves)

        # get move made
        move_made = getMoveMade(g)

        # get wdl stats
        positionWDL = getWDLStats(top_moves)

        # get evaluation
        try:
            current_best_move_evaluation = top_moves[0]["Centipawn"]
        except:
            current_best_move_evaluation = None

        # get piece moved
        piece_moved = getPieceMoved(move_made, stockfish)

        # store move
        current_move = {
            "fen": fen,
            "fullmove_number": g.board().fullmove_number,
            "legal_moves_count": g.board().legal_moves.count(),
            "white_to_move": g.turn(),
            "move_made": move_made.uci() if move_made else None,
            "piece_moved": piece_moved,
            "is_check": g.board().is_check(),
            "is_capture": g.board().is_capture(move_made) if move_made else None,
            "is_zeroing_move": g.board().is_zeroing(move_made) if move_made else None,
            "engine": {
                "name": ENGINE_NAME,
                "version": ENGINE_VERSION,
                "top_moves": top_moves,
                "wdl_before_move": positionWDL,
                "wdl_after_move": None,
                "evaluation_before_move": current_best_move_evaluation,
                "evaluation_after_move": None,
                "centipawnLoss": None,
            },
        }

        # in order to store centipawnloss, we need to have evaluated the next position
        # so we're storing
        if previous_move is not None:
            previous_move["engine"]["centipawnLoss"] = getCentipawnLoss(
                current_move, previous_move
            )
            previous_move["engine"][
                "evaluation_after_move"
            ] = current_best_move_evaluation
            previous_move["engine"]["wdl_after_move"] = positionWDL
            moves.append(previous_move)

        else:
            # first move
            moves.append(current_move)

        if DEBUG_LEVEL >= 3:
            print("\n\n")
            prettyPrint(previous_move)

        # store
        previous_move = current_move

    # cleanup headers
    cleanHeaders = {}
    for h in headers:
        cleanHeaders[h] = headers[h]

    # calc stats
    try:
        stats = getStats(moves)
    except Exception as e:
        stats = None
        print("stats error", str(e))
        pass

    # get pgn
    exporter = chess.pgn.StringExporter(headers=False, variations=False, comments=False)
    pgn_string = g.game().accept(exporter)

    # stored object
    evaluatedGame = {
        "moves": moves,
        "engine": {
            "parameters": stockfish.get_parameters(),
            "name": ENGINE_NAME,
            "version": ENGINE_VERSION,
        },
        "stats": stats,
        "headers": cleanHeaders,
        "pgn": pgn_string,
        "result": g.game().end().board().result(),
    }

    if DEBUG_LEVEL >= 2:
        print("\nEvaluated Game stats:")
        prettyPrint(evaluatedGame["stats"])

    gtoc = time.perf_counter()
    print("\n")
    print("Evaluated", len(moves), "moves")
    print(f"## Calculated the game in {gtoc - gtic:0.4f} seconds")
    print("\n")

    # write to file
    filevars = (
        cleanHeaders["Event"]
        + "-"
        + cleanHeaders["Site"]
        + "-"
        + cleanHeaders["Date"]
        + "-"
        + cleanHeaders["White"]
        + "-vs-"
        + cleanHeaders["Black"]
        + "-ply"
        + cleanHeaders["PlyCount"]
        + "-round"
        + cleanHeaders["Round"]
        + ".nodes"
        + str(ENGINE_NODES)
        + "."
        + ENGINE_NAME
        + str(ENGINE_VERSION)
    )

    gamefile = (
        CATCHFISH_FOLDER
        + "games/evals/"
        + ENGINE_NAME
        + str(ENGINE_VERSION)
        + "/"
        + slugify(filevars)
        + ".evaluation"
    )

    os.makedirs(os.path.dirname(gamefile), exist_ok=True)
    with open(gamefile, "w") as gf:
        gf.write(json.dumps(evaluatedGame))


def get_stockfish_versions():
    return [
        {"release_date": "2018-02-04", "version": 9, "nnue": False},
        {"release_date": "2018-12-01", "version": 10, "nnue": False},
        {"release_date": "2020-01-15", "version": 11, "nnue": False},
        {"release_date": "2020-09-02", "version": 12, "nnue": True},
        {"release_date": "2021-02-13", "version": 13, "nnue": True},
        {"release_date": "2021-07-02", "version": 14, "nnue": True},
        {"release_date": "2022-04-18", "version": 15, "nnue": True},
    ]


def get_stockfish_version(version=15):
    stockfish_versions = get_stockfish_versions()
    stockfish_version = pydash.find(stockfish_versions, {"version": version})
    return stockfish_version


def create_stockfish_instance(version=15, depth=21, mpv=10, threads=196, hash=4096):

    # get version dict
    stockfish_version = get_stockfish_version(version)

    ENGINE_VERSION = str(stockfish_version["version"])
    if DEBUG_LEVEL >= 1:
        print(
            "Initializing Stockfish version",
            ENGINE_VERSION,
            "Release date",
            stockfish_version["release_date"],
            "NNUE",
            stockfish_version["nnue"],
        )

    # init stockfish options
    stockfish_path = (
        "/home/ubuntu/catchfish/stockfish/stockfish-"
        + ENGINE_VERSION
        + "/stockfish-"
        + ENGINE_VERSION
    )

    stockfish_parameters = {
        "Threads": ENGINE_CPU_THREADS,  # cpu threads
        "Minimum Thinking Time": 1,
        "Debug Log File": "/home/ubuntu/catchfish/debug-log-stockfish-"
        + ENGINE_VERSION
        + ".log",
        "Hash": ENGINE_HASH_SIZE,
        "Ponder": False,
        "Skill Level": 20,
        "MultiPV": ENGINE_MPV_LINES,  # lines
    }

    # init stockfish
    stockfish = Stockfish(
        path=stockfish_path,
        depth=ENGINE_DEPTH,
        parameters=stockfish_parameters,
    )

    # print settings
    if DEBUG_LEVEL >= 2:
        print("Stockfish settings:")
        prettyPrint(stockfish.get_parameters())

    return stockfish


#        .
#       ":"
#     ___:____     |"\/"|
#   ,'        `.    \  /
#   |  O        \___/  |
# ~^~^~^~^~^~^~^~^~^~^~^~^~

# globals
ENGINE_NAME = "Stockfish"
ENGINE_VERSION = "0"
ENGINE_DEPTH = 21
ENGINE_NODES = 100000000
ENGINE_MPV_LINES = 10
ENGINE_CPU_THREADS = 196
ENGINE_HASH_SIZE = 4096
CATCHFISH_FOLDER = "/home/ubuntu/catchfish/"
DISABLE_CACHE = True
DEBUG_LEVEL = 2


# init redis
redis = redis.Redis(host="localhost", port="6379", db=5)

players = [
    "HansNiemann.pgn",
    "AndreyEsipenko.pgn",
    # 'ArjunErigaisi.pgn',
    # 'VincentKeymer.pgn',
    # 'AlirezaFirouzja.pgn',
    # 'NodirbekYakubboev.pgn',
    # 'SarinNihal.pgn',
    # 'Praggnanandhaa.pgn',
    # 'VincentKeymer.pgn',
    # 'NodirbekAbdusattorov.pgn',
    # 'DommarajuGukesh.pgn',
    # 'VishyAnand.pgn',
    # 'FabianoCaruana.pgn',
    # 'AnishGiri.pgn',
    # 'HikaruNakamura.pgn',
    # 'IanNepo.pgn',
    # 'WesleySo.pgn',
    # 'DingLiren.pgn',
    # 'LevonAronian.pgn',
    # 'MagnusCarlsen.pgn'
]

for player in players:
    file = CATCHFISH_FOLDER + "games/" + player
    print("Processing", file)
    evaluateGames(file)

print("\nDone!")
