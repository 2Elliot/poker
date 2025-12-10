"""
Aggressive Bot - Plays loose and aggressive
Bets and raises frequently, plays many hands
"""
from typing import List, Dict, Any
import random

from bot_api import PokerBotAPI, PlayerAction, GameInfoAPI
from engine.cards import Card, Rank
from engine.poker_game import GameState


class AggressiveBot(PokerBotAPI):
    """
    An aggressive bot that plays loose and raises frequently.
    Good example of an aggressive playing style.
    """
    
    def __init__(self, name: str):
        super().__init__(name)
        self.hands_played = 0
        self.raise_frequency = 0.4  # Raise 40% of the time when possible
        self.play_frequency = 0.7   # Play 70% of hands
        
    def get_action(self, game_state: GameState, hole_cards: List[Card], 
                   legal_actions: List[PlayerAction], min_bet: int, max_bet: int) -> tuple:
        """Play aggressively - bet and raise often"""
        
        if len(hole_cards) != 2:
            return PlayerAction.FOLD, 0
        
        card1, card2 = hole_cards
        
        # Evaluate hand strength (more lenient than conservative bot)
        hand_strength = self._evaluate_aggressive_hand_strength(card1, card2)
        
        # Fold very weak hands
        if hand_strength < 0.3 and random.random() > self.play_frequency:
            return PlayerAction.FOLD, 0
        
        # Get position and opponent info
        opponents = GameInfoAPI.get_active_opponents(game_state, self.name)
        position_info = GameInfoAPI.get_position_info(game_state, self.name)
        
        # More aggressive with fewer opponents
        aggression_multiplier = 1.5 if len(opponents) <= 2 else 1.0
        effective_raise_freq = min(0.6, self.raise_frequency * aggression_multiplier)
        
        # Decide action based on aggression
        if PlayerAction.RAISE in legal_actions and random.random() < effective_raise_freq:
            # Aggressive bet sizing
            current_pot = game_state.pot
            
            if hand_strength >= 0.6:  # Very strong hand
                # Big raise
                raise_amount = min(game_state.current_bet + current_pot, max_bet)
            elif hand_strength >= 0.4:  # Good hand
                # Medium raise
                raise_amount = min(game_state.current_bet + current_pot // 2, max_bet)
            else:  # Bluff with weaker hands
                # Small raise (bluff)
                raise_amount = min(game_state.current_bet + current_pot // 4, max_bet)
            
            raise_amount = max(raise_amount, min_bet)  # Ensure minimum
            return PlayerAction.RAISE, raise_amount
        
        elif PlayerAction.CALL in legal_actions:
            # Call most of the time if we can't or don't want to raise
            to_call = GameInfoAPI.calculate_bet_amount(game_state.current_bet, 
                                                     game_state.player_bets[self.name])
            
            # Calculate pot odds
            pot_odds = GameInfoAPI.get_pot_odds(game_state.pot, to_call) if to_call > 0 else float('inf')
            
            # Aggressive calling - call with weaker hands than normal
            if hand_strength >= 0.4 or pot_odds > 2.0:
                return PlayerAction.CALL, 0
        
        elif PlayerAction.CHECK in legal_actions:
            return PlayerAction.CHECK, 0
        
        # Default to fold
        return PlayerAction.FOLD, 0
    
    def _evaluate_aggressive_hand_strength(self, card1: Card, card2: Card) -> float:
        """
        Evaluate hand strength from aggressive perspective
        More lenient than conservative evaluation
        """
        # Pocket pairs are always good
        if card1.rank == card2.rank:
            if card1.rank.value >= 7:  # 7s or better
                return 0.9
            else:  # Small pairs still playable
                return 0.6
        
        # High cards
        high_card = max(card1.rank.value, card2.rank.value)
        low_card = min(card1.rank.value, card2.rank.value)
        
        # Bonuses for suited/connected
        suited_bonus = 0.15 if card1.suit == card2.suit else 0.0
        connected_bonus = 0.1 if abs(card1.rank.value - card2.rank.value) <= 2 else 0.0
        
        # More lenient high card requirements
        if high_card >= 12:  # Queen or better
            base_strength = 0.7
        elif high_card >= 10:  # Ten or Jack
            base_strength = 0.5
        elif high_card >= 8:   # 8 or 9
            base_strength = 0.4
        else:
            base_strength = 0.2
        
        # Bonus for decent low card
        if low_card >= 8:
            base_strength += 0.2
        elif low_card >= 6:
            base_strength += 0.1
        
        # Face cards together
        if high_card >= 11 and low_card >= 11:
            base_strength += 0.1
        
        return min(1.0, base_strength + suited_bonus + connected_bonus)
    
    def hand_complete(self, game_state: GameState, hand_result: Dict[str, Any]):
        """Track aggressive play results"""
        self.hands_played += 1
        
        # Learn from results - adjust aggression slightly
        if 'winners' in hand_result:
            if self.name in hand_result['winners']:
                # Won - maybe be slightly more aggressive
                self.raise_frequency = min(0.6, self.raise_frequency + 0.01)
            else:
                # Lost - maybe tone down aggression slightly
                self.raise_frequency = max(0.2, self.raise_frequency - 0.005)
        
        # Log statistics every 20 hands
        if self.hands_played % 20 == 0:
            self.logger.info(f"Aggressive play: {self.hands_played} hands, " +
                           f"current raise frequency: {self.raise_frequency:.2%}")
    
    def tournament_start(self, players: List[str], starting_chips: int):
        """Adjust initial aggression based on field size"""
        super().tournament_start(players, starting_chips)
        
        # More aggressive with fewer players
        if len(players) <= 4:
            self.raise_frequency = 0.5
            self.play_frequency = 0.8
        elif len(players) >= 8:
            self.raise_frequency = 0.3
            self.play_frequency = 0.6