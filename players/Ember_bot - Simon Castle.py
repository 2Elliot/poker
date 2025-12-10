from typing import List, Dict, Any
import random
import math

from bot_api import PokerBotAPI, PlayerAction, GameInfoAPI
from engine.cards import Card, Rank, HandEvaluator
from engine.poker_game import GameState


class EmberBot(PokerBotAPI):
    """
    A generally aggressive bot that folds quickly with a poor hand but raises aggressively with a good hand.
    """
    
    def __init__(self, name: str):
        super().__init__(name)
        self.hands_played = 0  # Track hands played
        self.raise_frequency = 1.0  # Default raise frequency
        self.play_frequency = 1.0 # Play 100% of hands by default
        self.is_good_hole = False
        
    def get_action(self, game_state: GameState, hole_cards: List[Card], 
                   legal_actions: List[PlayerAction], min_bet: int, max_bet: int) -> tuple:
        """Play aggressively - bet and raise often"""
        
        self.raise_frequency = 1.0
        self.play_frequency = 1.0
        self.is_good_hole = False

        if game_state.round_name == "preflop":
            return self._preflop_strategy(game_state, hole_cards, legal_actions, min_bet, max_bet)
        else:
            return self._postflop_strategy(game_state, hole_cards, legal_actions, min_bet, max_bet)
        

    def _preflop_strategy(self, game_state: GameState, hole_cards: List[Card], legal_actions: List[PlayerAction], 
                          min_bet: int, max_bet: int) -> tuple:
        """Aggressive pre-flop strategy"""
        
        # Get value of hole cards
        card1_value = hole_cards[0].rank.value
        card2_value = hole_cards[1].rank.value
        card1_suit = hole_cards[0].suit
        card2_suit = hole_cards[1].suit
        hole_average = (card1_value + card2_value) / 2
        hole_suited = card1_suit == card2_suit
        hole_difference = abs(card1_value - card2_value)
    

        # Check if hole cards are a pair
        if hole_average >= 10:
            if hole_suited and hole_average >= 11 and hole_difference <= 1:
                self.is_good_hole = True
            elif card1_value == card2_value:
                self.is_good_hole = True
            elif hole_suited and hole_difference <= 1 and hole_average >= 12:
                if random.random() >= 0.05: # 95% chance to raise
                    return PlayerAction.RAISE, max(min_bet, min(max_bet, (max_bet - (int(max_bet / 20)))))
                else:
                    self.is_good_hole = True
        
        if self.is_good_hole == False:
            self.play_frequency = 0.04


        if random.random() < self.play_frequency:
            if PlayerAction.RAISE in legal_actions and random.random() < self.raise_frequency:
                    # Raise 3-4x the big blind
                    raise_amount = min(random.randint(3, 4) * game_state.big_blind, max_bet)
                    raise_amount = max(raise_amount, min_bet)
                    return PlayerAction.RAISE, raise_amount
            
        if GameInfoAPI.get_position_info(game_state, player_name = "Ember_bot") == "is_last":
            if PlayerAction.CHECK in legal_actions:
                return PlayerAction.CHECK, 0

        return PlayerAction.FOLD, 0

    def _postflop_strategy(self, game_state: GameState, hole_cards: List[Card], 
                           legal_actions: List[PlayerAction], min_bet: int, max_bet: int) -> tuple:
        """Aggressive post-flop strategy"""
        all_cards = hole_cards + game_state.community_cards
        hand_type, _, _ = HandEvaluator.evaluate_best_hand(all_cards)
        hand_rank = HandEvaluator.HAND_RANKINGS[hand_type]

        # Strong hand (top pair or better)
        if hand_rank >= HandEvaluator.HAND_RANKINGS['flush']:
            if random.random() < 0.9: # 90% chance to raise
                if PlayerAction.RAISE in legal_actions:
                    if int(game_state.big_blind * 3) < (max_bet - (int(max_bet / 20))):
                        return PlayerAction.RAISE, max(min_bet, min(max_bet, int(game_state.big_blind * 3)))
                    else:
                        return PlayerAction.RAISE, max(min_bet, min(max_bet, (max_bet - (int(max_bet / 20)))))
                else:
                    if PlayerAction.CALL in legal_actions:
                        return PlayerAction.CALL, 0

        
        if hand_rank >= HandEvaluator.HAND_RANKINGS['pair']:
            if random.random() < 0.5: # 50% chance to raise
                if PlayerAction.RAISE in legal_actions:
                    if int(game_state.big_blind * 1.2) < (max_bet - (int(max_bet / 20))):
                        return PlayerAction.RAISE, max(min_bet, min(max_bet, int(game_state.big_blind * 1.2)))
                    else:
                        return PlayerAction.RAISE, max(min_bet, min(max_bet, (max_bet - (int(max_bet / 20)))))

                        
            else:
                if PlayerAction.CHECK in legal_actions:
                    return PlayerAction.CHECK, 0

                elif PlayerAction.CALL in legal_actions:
                    return PlayerAction.CALL, 0

        if random.random() < 0.005: # 0.5% chance to raise
            if PlayerAction.RAISE in legal_actions:
                return PlayerAction.RAISE, max(min_bet, min(max_bet, (max_bet - (int(max_bet / 20)))))

        return PlayerAction.FOLD, 0
    
    def hand_complete(self, game_state: GameState, hand_result: Dict[str, Any]):
        self.hands_played += 1
        if 'winners' in hand_result and self.name in hand_result['winners']:
            # Won - be more aggressive
            self.raise_frequency = min(0.7, self.raise_frequency + 0.02)
        else:
            # Lost - tone it down
            self.raise_frequency = max(0.3, self.raise_frequency - 0.01)
    
    def tournament_start(self, players: List[str], starting_chips: int):
        super().tournament_start(players, starting_chips)
        if len(players) <= 4:
            self.raise_frequency = 0.6
            self.play_frequency = 0.9
        elif len(players) >= 8:
            self.raise_frequency = 0.4
            self.play_frequency = 0.7