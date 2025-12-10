from typing import List, Dict, Any

from bot_api import PokerBotAPI, PlayerAction, GameInfoAPI
from engine.cards import Card, Rank
from engine.poker_game import GameState


class AlwaysFold(PokerBotAPI):
    
    def __init__(self, name: str):
        super().__init__(name)
        
    def get_action(self, game_state: GameState, hole_cards: List[Card], 
                   legal_actions: List[PlayerAction], min_bet: int, max_bet: int) -> tuple:
        return PlayerAction.FOLD, 0
    
    def hand_complete(self, game_state: GameState, hand_result: Dict[str, Any]):
        pass
    
    def tournament_start(self, players: List[str], starting_chips: int):
        pass