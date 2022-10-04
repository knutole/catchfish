from catchfish import Catchfish, Analysis
import json

log_level = "none"
catchfish = Catchfish(log_level=log_level)

# game_key = "game:559565a51c704d7543d93b6117ba8e36"
# game_key = "game:865747104611069c23e9a765377002a4"
# game = {
#     "description": "Carlsen, Magnus vs Niemann, Hans Moke 2022.08.16 1-0 FTX Crypto Cup 2022",
#     "key": "game:5d16546f3e036c3057c6fc2f993d9087",
# }

game = {
    "description": "Le, Quang Liem vs Carlsen, Magnus 2022.08.18 1/2-1/2 FTX Crypto Cup 2022",
    "key": "game:f964dc71653044e7408a9f68da0b7403",
}  # mc 13, 10 (21) |

evaluation = catchfish.get_evaluation_by_key(game["key"])

a = Analysis(evaluation=json.loads(evaluation), log_level=log_level)
result = a.analyse(return_move_data=True)
print(result)
