import copy
from constants import Constants

# あなたのプロジェクトで最も強いAIをインポート
from ai.world_class_ai import WorldAI


class GameAnalyzer:
    """盤面を分析してアドバイスを提供するクラス"""

    def __init__(self):
        self.ai = None

    def analyze(self, game_logic):
        """
        現在の盤面を受け取り、AIが考える最善手を返す
        戻り値: (x, y) のタプル、または打てる場所がない場合は None
        """
        # 1. 盤面状態を壊さないようにDeepCopy
        copied_logic = copy.deepcopy(game_logic)

        # 2. AIインスタンスを作成
        analyzer_ai = WorldAI(copied_logic)

        # 3. WorldAIが計算できる形式（intの2次元配列）にデータを変換
        #    WorldAI内のヘルパーメソッドを利用します
        raw_board = copied_logic.board
        current_turn = copied_logic.state.turn

        ai_board = analyzer_ai._convert_board(raw_board)
        ai_player = analyzer_ai._convert_to_ai_player(current_turn)

        # 4. AIに思考させる
        #    get_move(board, player, time_limit) を呼び出す
        #    ※アドバイス用なので時間は短め(2秒)に設定していますが、
        #      精度を上げたい場合は time_limit=5 などにしてください
        best_move = analyzer_ai.get_move(ai_board, ai_player, time_limit=5)

        return best_move
