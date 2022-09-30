from catchfish import Analysis, RedisStore, Game, Games, Evaluation, StockfishVariant
import sys, os


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

# e = Evaluation()
# game_evaluation = e.get_result_by_key("822b5959df9e1b1bd3832528cf4aac8c")
# a = Analysis(evaluation=game_evaluation, debug_level=4)
# a.analyse()
# # print(e.get_result_by_key("dfee4b3f426559b39343a0c36ab8f88a"))
# sys.exit()

# example
#
# - got a path to pgn
# - want to evaluate all games
# - with a matrix of SF versions and depths/nodes
# - return results of evaluation
#

# file = os.path.join(os.path.dirname(__file__), "tests/" "AlirezaFirouzja.pgn")

# for game in games.get_games():
#     for position in game.get_positions():
#         print(game.get_info(), position)

# for game in games.get_games():
#     # print(game._headers)
#     # print(game.get_headers())
#     print("white", game.get_info()["white"])
#     print("black", game.get_info()["black"])
#     print("white_elo", game.get_info()["white_elo"])
#     print("black_elo", game.get_info()["black_elo"])
#     print("ply", game.get_info()["ply"])
# print(game.get_info()) #


def read_games(path, limit_games=0):
    # file = os.path.join(os.path.dirname(__file__), "tests/" "SusNiemann.pgn")
    file = os.path.join(os.path.dirname(__file__), path)
    games = Games(path=file, limit_games=limit_games, validate_fen=True)
    print("Invalid games", games.get_invalid_games())
    return games


def run_evaluation(games):
    evaluation = Evaluation(
        games=games,
        # games=None,
        # stockfish_versions=[10, 12, 15],
        stockfish_versions=[15],
        historical=True,
        debug_level=2,
        threads=196,
        hash=4096,
        depth=20,
        multi_pv=5,
        # num_nodes=["5M", "10M", "20M"],
        num_nodes=["30M"],
        mode="nodes",
        engine_log_file="/home/ubuntu/catchfish/catchfish/analysis.log",
    )

    keys = evaluation.evaluate()

    # print("All done!", evaluation.get_results())
    print("All done!", evaluation.get_result_keys())
    print("All done!", keys)
    return keys

    # key = "c120e0cf57de267a3e14f9668e6ec1bb"
    # print("All done!", evaluation.get_result_by_key(key))

    # silicon strength
    # - iphone 13 can do 1M N/s, ie. 30M nodes in 30 seconds.
    # - samsung 2018 ?
    # - iphone 2020 ? etc
    # - laptop
    # - strong laptop
    # - desktop
    # - strong desktop
    # - supercomputer


def run_analysis(key):
    e = Evaluation()
    evaluation = e.get_result_by_key(key)
    a = Analysis(evaluation=evaluation, debug_level=4)
    a.analyse()


# run_analysis(key="a90a80d57c96f5e9497b0cabca11298e")
# run_analysis(key="8641a41f96b21b0e4011b03512cb06f9")
# run_analysis(key="d7c8b7a62d515fe4b5e97f54d4e73619")
# run_analysis(key="5c53027073bfd6240656081ecc27b49c")
# run_analysis(key="f51adfd50c4d725e792688756ea44963")
# run_analysis(key="9d984d931323d23e0df1463c5a8cd601")
# run_analysis(key="0592620cef366ed55cb64fe56a0d6180")
# run_analysis(key="2602d7b9345c4df4de2d2cc86e0c4fe1")
# run_analysis(key="3d11a60fde39baec7ea0fd562d864d2e")

games = read_games("tests/SusNiemann.pgn", limit_games=2)
keys = run_evaluation(games)
