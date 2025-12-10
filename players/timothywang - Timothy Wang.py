"""
Conservative Bot - Plays very tight and safe
Only plays strong hands and folds most of the time
"""
from typing import List, Dict, Any, Tuple
import random
from bot_api import PokerBotAPI, PlayerAction, GameInfoAPI
from engine.cards import Card, Rank, HandEvaluator
from engine.poker_game import GameState, PokerGame


class ConservativeBot(PokerBotAPI):
    """
    A conservative bot that only plays very strong hands.
    Good example of a tight playing style.
    """
    def __init__(self, name: str):
        super().__init__(name)
        self.hands_played = 0
        self.hands_won = 0
        
    
    def get_action(self, game_state: GameState, hole_cards: List[Card], 
                   legal_actions: List[PlayerAction], min_bet: int, max_bet: int) -> tuple:
        """Play very conservatively - only strong hands pre-flop, then evaluate post-flop"""
        
        if game_state.round_name == "preflop":
            return self._preflop_strategy(game_state, hole_cards, legal_actions, min_bet, max_bet)
        else:
            return self._postflop_strategy(game_state, hole_cards, legal_actions, min_bet, max_bet)



    def _preflop_strategy(self, game_state: GameState, hole_cards: List[Card], legal_actions: List[PlayerAction], 
                          min_bet: int, max_bet: int) -> tuple:
        """Strategy for pre-flop betting"""
        if len(hole_cards) != 2:
            return PlayerAction.FOLD, 0
        
        card1, card2 = hole_cards
        is_pocket_pair = card1.rank == card2.rank
        
        #Two conditions deprecated for more aggressive play, force to at least see the flop if has a strong card - high crad pay towards

        #is_suit_match = card1.suit == card2.suit

        #is_straight_potential = abs(card1.rank.value - card2.rank.value) <= 3

        # pocket pair very strong hand - raise to the ceiling, maybe cap high
        if is_pocket_pair:
            if PlayerAction.RAISE in legal_actions:
                    # print("Pocket Pair detected, raising")
                    return PlayerAction.RAISE, min_bet
            
            
        # use numeric rank values for comparisons
        highest_rank_value = max(card1.rank.value, card2.rank.value)
        if highest_rank_value >= Rank.TEN.value:
            # print("High card detected, calling or checking")
            if PlayerAction.CALL in legal_actions:
                if game_state.current_bet < (game_state.big_blind * 10):
                    # print("High card call")
                    return PlayerAction.CALL, 0
            elif PlayerAction.CHECK in legal_actions:
                # print("High card check")
                return PlayerAction.CHECK, 0
        else:
            # print("No strong cards, folding")
            return PlayerAction.FOLD, 0
        # print("Fail saf fold")
        return PlayerAction.FOLD, 0
        
            


    def _postflop_strategy(self, game_state: GameState, hole_cards: List[Card], 
                           legal_actions: List[PlayerAction], min_bet: int, max_bet: int) -> tuple:
        """Strategy for post-flop betting (flop, turn, river)"""
        
        all_cards = hole_cards + game_state.community_cards
        hand_type, _, _ = HandEvaluator.evaluate_best_hand(all_cards)
        hand_rank = HandEvaluator.HAND_RANKINGS[hand_type]

        # determine highest hole-card rank value once, and comunity high rank
        highest_hole_rank = max((c.rank.value for c in hole_cards), default=0)
        community_max_rank = max((c.rank.value for c in game_state.community_cards), default=0)

        # Strong hand (two pair or better)
        if hand_rank >= HandEvaluator.HAND_RANKINGS['two_pair']:
            public_stregth = self.public_stregth_check(game_state,hole_cards)
            if public_stregth:
                # Public hand matches ours, play cautiously
                if highest_hole_rank >= community_max_rank:
                    #Has strong high, be more aggressive
                    if PlayerAction.RAISE in legal_actions:
                        return PlayerAction.RAISE, min_bet
                    if PlayerAction.CALL in legal_actions:
                        return PlayerAction.CALL, 0
                else:
                    if PlayerAction.CHECK in legal_actions:
                        return PlayerAction.CHECK, 0
                    if PlayerAction.FOLD in legal_actions:
                        return PlayerAction.FOLD, 0
            else:
                # Public hand weaker, be more aggressive
                if PlayerAction.RAISE in legal_actions:
                    return PlayerAction.RAISE, min_bet
                if PlayerAction.CALL in legal_actions:
                    return PlayerAction.CALL, 0

        # Decent hand (pair)
        if hand_rank == HandEvaluator.HAND_RANKINGS['pair']:
            public_stregth = self.public_stregth_check(game_state,hole_cards)
            if public_stregth:
                    if highest_hole_rank >=community_max_rank: 
                        if PlayerAction.CHECK in legal_actions:
                            return PlayerAction.CHECK, 0
                        if PlayerAction.CALL in legal_actions:
                            return PlayerAction.CALL, 0
                    else:
                        if PlayerAction.CHECK in legal_actions:
                            return PlayerAction.CHECK, 0
                        if PlayerAction.FOLD in legal_actions:
                            return PlayerAction.FOLD, 0    
        # Drawing hands
        if self._has_strong_draw(all_cards):
            if PlayerAction.CHECK in legal_actions:
                return PlayerAction.CHECK, 0
            if PlayerAction.CALL in legal_actions:
                return PlayerAction.CALL, 0



        # Nothing good, fold
        if PlayerAction.CHECK in legal_actions:
            return PlayerAction.CHECK, 0
        return PlayerAction.FOLD, 0

    def _has_strong_draw(self, all_cards: List[Card]) -> bool:
        """Check for strong drawing hands (flush or open-ended straight)"""
        # Flush draw
        suits = [card.suit for card in all_cards]
        for suit in set(suits):
            if suits.count(suit) == 4:
                return True
        
        # Open-ended straight draw
        #ranks = sorted(list(set(card.rank.value for card in all_cards)))
        #for i in range(len(ranks) - 3):
            #if ranks[i+3] - ranks[i] == 3 and len(ranks) >=4 :
                 # e.g., 5,6,7,8
                #return True


        return False

    def hand_complete(self, game_state: GameState, hand_result: Dict[str, Any]):
        """Track conservative play results"""
        self.hands_played += 1
        if 'winners' in hand_result and self.name in hand_result['winners']:
            self.hands_won += 1
        
        if self.hands_played > 0 and self.hands_played % 25 == 0:
            win_rate = self.hands_won / self.hands_played
            self.logger.info(f"Conservative play: {self.hands_won}/{self.hands_played} wins ({win_rate:.2%})")

    def public_stregth_check(self, game_state: GameState, hole_cards: List[Card]) -> bool:
        """Provide public strength assessment.

        Only compare full 5-card public hands (river). For flop/turn there aren't
        enough community cards to build a 5-card hand, so return False to avoid
        calling HandEvaluator.evaluate_best_hand on too few cards.
        """
        public_cards = game_state.community_cards

        # HandEvaluator.evaluate_best_hand requires at least 5 cards.
        if len(public_cards) < 5:
            return False

        all_cards = public_cards + hole_cards
        public_hand_type, _, _ = HandEvaluator.evaluate_best_hand(public_cards)
        my_hand_type, _, _ = HandEvaluator.evaluate_best_hand(all_cards)
        return public_hand_type == my_hand_type