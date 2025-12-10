"""
Thomas Dobratz Bot - We shall see how it plays
This is the bot I am entering in the tournament
"""
from typing import List, Dict, Any
import random

from bot_api import PokerBotAPI, PlayerAction
from engine.cards import Card
from engine.poker_game import GameState

class ThomasDobratzBot(PokerBotAPI):
    """
    This is the poker bot entered by Thomas Dobratz.
    Hopefully it does well.
    """

    def __init__(self, name: str):
        super().__init__(name)
        self.hands_played = 0
    
    def get_action(self, game_state: GameState, hole_cards: List[Card], 
                   legal_actions: List[PlayerAction], min_bet: int, max_bet: int) -> tuple:
        """This handles the decision making."""
        
        # Choose a random legal action
        action = random.choice(legal_actions)
        
        # If raising, choose a random valid amount
        if action == PlayerAction.RAISE:
            # More realistic random raise - between min raise and pot size
            max_raise = min(game_state.pot * 1.5, max_bet) # Raise up to 1.5x pot
            if max_raise < min_bet:
                max_raise = min_bet
                
            amount = random.randint(min_bet, int(max_raise))
            return action, amount
        
        # All other actions don't need an amount
        return action, 0
    
    def hand_complete(self, game_state: GameState, hand_result: Dict[str, Any]):
        """Track hands played"""
        self.hands_played += 1
        
        if self.hands_played > 0 and self.hands_played % 50 == 0:
            self.logger.info(f"Played {self.hands_played} hands randomly")