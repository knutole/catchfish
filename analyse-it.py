from catchfish import Catchfish, Analysis
import json

catchfish = Catchfish(log_level="debug")

# game_key = "game:559565a51c704d7543d93b6117ba8e36"
game_key = "game:865747104611069c23e9a765377002a4"
evaluation = catchfish.get_evaluation_by_key(game_key)

a = Analysis(evaluation=json.loads(evaluation), log_level="debug")
result = a.analyse()
print("All done!", result)
print("All done!")

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
