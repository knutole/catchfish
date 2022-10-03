from catchfish import (
    Catchfish,
    Analysis,
    RedisStore,
    Game,
    Games,
    Evaluation,
    StockfishVariant,
)
import sys, os


def read_games(path, limit_games=0):
    file = os.path.join(os.path.dirname(__file__), path)
    games = Games(path=file, limit_games=limit_games, validate_fen=True, debug_level=2)
    print("Invalid games", games.get_invalid_games_count())
    return games


def run_evaluation(games):
    evaluation = Evaluation(
        games=games,
        # games=None,
        # stockfish_versions=[10, 12, 15],
        stockfish_versions=[15, 14, 13, 12, 11],
        historical=True,
        debug_level=2,
        # threads=196,
        threads=128,
        hash=32768,
        depth=20,
        multi_pv=10,
        num_nodes=[
            "200M",
        ],
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


def run_analysis(key, debug_level=2):
    e = Evaluation(debug_level=debug_level)
    evaluation = e.get_result_by_key(key)
    a = Analysis(evaluation=evaluation, debug_level=debug_level)
    result = a.analyse()
    print("All done!", result)


# test
catchfish = Catchfish(
    # defaults
    limit_games=0,
    stockfish_versions=[15],
    # historical=True,
    log_level="info",
    threads=128,
    # hash_size=131072,
    hash_size=0,
    depth=20,
    multi_pv=5,
    num_nodes=["200M"],
    mode="nodes",
    engine_log_file="zero-hash-debug.log",
    raw_output=True,
    # cache=True,
)
# catchfish.load_games("tests/SusNiemann.pgn")
catchfish.load_games("tests/FTXCryptoCup2022.pgn")
# catchfish.load_games("tests/HansNiemann.pgn")
# catchfish.load_games("tests/kanov-niemann.pgn")
catchfish.evaluate()
print("All done!")


# # test
# catchfish = Catchfish(
#     # defaults
#     limit_games=0,
#     stockfish_versions=[15],
#     # historical=True,
#     log_level="info",
#     threads=128,
#     hash_size=131072,
#     depth=20,
#     multi_pv=5,
#     num_nodes=["200M"],
#     mode="nodes",
#     engine_log_file="debug.log",
#     raw_output=True,
#     # cache=True,
# )

# print(catchfish.get_evaluation_by_key("game:5f7ddd291d6ae96ae6301287a6087832"))
