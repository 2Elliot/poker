from typing import List, Dict, Any
import random

from bot_api import PokerBotAPI, PlayerAction, GameInfoAPI
from engine.cards import Card, Rank, HandEvaluator
from engine.poker_game import GameState


class SebastianBot(PokerBotAPI):
    def __init__(self, name: str):
        super().__init__(name)
        self.hands_played = 0
        self.raise_frequency = 0.5  # Default raise frequency
        self.play_frequency = 0.8   # Play 80% of hands
        # Simple opponent profiling: track raises seen per player
        self.opponent_raise_counts = {}
        self.opponent_hand_counts = {}
        # Position (will be set on tournament_start if provided)
        self.position = None
        # 3-bet bluff frequency (small controlled percentage)
        self.three_bet_bluff_freq = 0.12
        # Track simple cbet/fold stats (very basic counters)
        self.opponent_fold_to_cbet = {}
        self.opponent_cbet_count = {}
        
    def get_action(self, game_state: GameState, hole_cards: List[Card], 
                   legal_actions: List[PlayerAction], min_bet: int, max_bet: int) -> tuple:
        """Play aggressively - bet and raise often"""
        
        if game_state.round_name == "preflop":
            return self._preflop_strategy(game_state, hole_cards, legal_actions, min_bet, max_bet)
        else:
            return self._postflop_strategy(game_state, hole_cards, legal_actions, min_bet, max_bet)

    def _preflop_strategy(self, game_state: GameState, hole_cards: List[Card], legal_actions: List[PlayerAction], 
                          min_bet: int, max_bet: int) -> tuple:
        """Aggressive pre-flop strategy"""
        # Position-aware and opponent-aware preflop decisions
        # Track basic opponent behavior
        for player, info in getattr(game_state, 'last_actions', {}).items():
            # last_actions may contain tuples like (action, amount)
            act = info[0] if isinstance(info, tuple) and info else info
            if act == PlayerAction.RAISE:
                self.opponent_raise_counts[player] = self.opponent_raise_counts.get(player, 0) + 1
            self.opponent_hand_counts[player] = self.opponent_hand_counts.get(player, 0) + 1

        # Determine simple open-raiser in front of us (if any)
        open_raiser = getattr(game_state, 'last_open_raiser', None)

        # If we are facing an open-raise in late position from a frequent raiser, widen defending range
        facing_raise = open_raiser is not None and open_raiser != self.name

        # If in blinds, defend wider
        in_small_blind = getattr(game_state, 'is_small_blind', False) and game_state.player_to_act == self.name
        in_big_blind = getattr(game_state, 'is_big_blind', False) and game_state.player_to_act == self.name

        # Determine base preflop strength
        strong = self._is_strong_preflop(hole_cards)

        # Widen range when defending blinds or facing frequent raiser
        if (in_small_blind or in_big_blind or (facing_raise and self._is_opponent_aggressive(open_raiser))):
            strong = strong or self._is_worth_defending(hole_cards)

        # If facing an open-raise, consider a 3-bet: value 3-bets plus occasional bluffs
        if facing_raise and PlayerAction.RAISE in legal_actions:
            # Strong value 3-bet hands
            if self._is_3bet_hand(hole_cards):
                raise_amount = min(max(3 * game_state.big_blind, int(game_state.current_bet * 3)), max_bet)
                raise_amount = max(raise_amount, min_bet)
                return PlayerAction.RAISE, raise_amount

            # Controlled 3-bet bluff when in position or defending blinds
            in_position = getattr(game_state, 'is_button', False) or getattr(game_state, 'is_cutoff', False)
            if (in_position or in_small_blind or in_big_blind) and random.random() < self.three_bet_bluff_freq:
                raise_amount = min(max(2 * game_state.big_blind, int(game_state.current_bet * 2)), max_bet)
                raise_amount = max(raise_amount, min_bet)
                return PlayerAction.RAISE, raise_amount

        if not strong:
            if PlayerAction.CHECK in legal_actions:
                return PlayerAction.CHECK, 0
            return PlayerAction.FOLD, 0

        # High probability of raising
        if PlayerAction.RAISE in legal_actions and random.random() < self.raise_frequency:
            # Raise 3-4x the big blind
            raise_amount = min(random.randint(3, 4) * game_state.big_blind, max_bet)
            raise_amount = max(raise_amount, min_bet)
            return PlayerAction.RAISE, raise_amount
        
        if PlayerAction.CALL in legal_actions:
            return PlayerAction.CALL, 0
            
        return PlayerAction.CHECK, 0

    def _is_3bet_hand(self, hole_cards: List[Card]) -> bool:
        """Very tight 3-bet range: QQ+, AK, AJs+"""
        if not hole_cards or len(hole_cards) != 2:
            return False
        r1 = hole_cards[0].rank.value
        r2 = hole_cards[1].rank.value
        suited = hole_cards[0].suit == hole_cards[1].suit
        hi = max(r1, r2)
        lo = min(r1, r2)

        # Pocket QQ+
        if r1 == r2 and r1 >= 12:
            return True

        # AK (suited or not)
        if {r1, r2} == {14, 13}:
            return True

        # AJs+ (suited)
        if hi == 14 and lo >= 11 and suited:
            return True

        return False

    def _is_opponent_aggressive(self, player_name: str) -> bool:
        """Return True if opponent raised frequently in observed hands."""
        if not player_name:
            return False
        raises = self.opponent_raise_counts.get(player_name, 0)
        hands = self.opponent_hand_counts.get(player_name, 1)
        # If raise rate > 25% treat as aggressive
        return (raises / hands) > 0.25

    def _is_worth_defending(self, hole_cards: List[Card]) -> bool:
        """Wider defending range for blinds and vs steals: include more pockets, Axs, and connectors"""
        if not hole_cards or len(hole_cards) != 2:
            return False
        r1 = hole_cards[0].rank.value
        r2 = hole_cards[1].rank.value
        suited = hole_cards[0].suit == hole_cards[1].suit
        hi = max(r1, r2)
        lo = min(r1, r2)

        # Defend pocket pairs 5+
        if r1 == r2 and r1 >= 5:
            return True

        # Defend A-x suited down to A6s
        if hi == 14 and suited and lo >= 6:
            return True

        # Defend suited connectors down to 76s
        if suited and (hi - lo == 1) and lo >= 6:
            return True

        # Defend broadway offsuit with decent kickers (AQ, AJ, KQ)
        if hi >= 12 and lo >= 10:
            return True

        return False

    def _is_strong_preflop(self, hole_cards: List[Card]) -> bool:
        """Simple starting-hand filter: returns True for hands worth playing preflop.

        Heuristics used:
        - Always play pocket pairs of 7s or higher.
        - Play any pair 6 or lower only rarely (treated as weak here -> fold).
        - Play broadway combinations: A-K, A-Q, A-J, K-Q (preferably suited).
        - Play suited connectors of 9-10 and higher (e.g., T9s, JTs), and suited A with decent kicker.
        - Otherwise fold.
        """
        if not hole_cards or len(hole_cards) != 2:
            return False

        r1 = hole_cards[0].rank.value
        r2 = hole_cards[1].rank.value
        suited = hole_cards[0].suit == hole_cards[1].suit

        hi = max(r1, r2)
        lo = min(r1, r2)

        # Pocket pairs
        if r1 == r2:
            # Play 7s+ aggressively
            return r1 >= 7

        # Strong Broadway combos
        if {hi, lo} <= {14, 13}:
            return True  # AK
        if hi == 14 and lo >= 11:  # A-Q, A-J
            return True
        if hi == 13 and lo >= 12 and suited:  # KQ suited
            return True

        # Suited A with decent kicker (A with 9+ suited)
        if hi == 14 and suited and lo >= 9:
            return True

        # Suited connectors 10-J, J-Q, T9 suited
        if suited and (hi - lo == 1) and lo >= 9:
            return True

        # Small connectors and one-gappers are too speculative here
        return False

    def _postflop_strategy(self, game_state: GameState, hole_cards: List[Card], 
                           legal_actions: List[PlayerAction], min_bet: int, max_bet: int) -> tuple:
        """Aggressive post-flop strategy"""
        all_cards = hole_cards + game_state.community_cards
        hand_type, _, _ = HandEvaluator.evaluate_best_hand(all_cards)
        hand_rank = HandEvaluator.HAND_RANKINGS[hand_type]

        # Strong hand (top pair or better)
        if hand_rank >= HandEvaluator.HAND_RANKINGS['pair']:
            if PlayerAction.RAISE in legal_actions:
                # Bet 2/3 to full pot
                raise_amount = min(game_state.pot, max_bet)
                raise_amount = max(raise_amount, min_bet)
                return PlayerAction.RAISE, raise_amount
            if PlayerAction.CALL in legal_actions:
                return PlayerAction.CALL, 0
        
        # Strong draw - play aggressively (semi-bluff)
        if self._has_strong_draw(all_cards):
            if PlayerAction.RAISE in legal_actions:
                 # Bet half pot on a draw
                raise_amount = min(game_state.pot // 2, max_bet)
                raise_amount = max(raise_amount, min_bet)
                return PlayerAction.RAISE, raise_amount
            if PlayerAction.CALL in legal_actions:
                return PlayerAction.CALL, 0

        # Pot-odds based calling for draws / marginal pairs
        # Determine amount to call
        to_call = 0
        if hasattr(game_state, 'current_bet') and hasattr(game_state, 'player_bets'):
            to_call = game_state.current_bet - game_state.player_bets.get(self.name, 0)
        # Avoid negative
        to_call = max(0, int(to_call))

        # If we have a draw or single pair, consider calling based on simple pot odds
        if to_call > 0 and PlayerAction.CALL in legal_actions:
            pot = game_state.pot
            # Pot odds: fraction you must invest to call
            pot_odds = to_call / (pot + to_call)

            # If we have a flush or open-ended straight draw, call if pot odds < 0.25
            if self._has_strong_draw(all_cards) and pot_odds < 0.25:
                return PlayerAction.CALL, 0

            # If we have at least a pair and pot_odds reasonable, call
            if hand_rank >= HandEvaluator.HAND_RANKINGS['pair'] and pot_odds < 0.4:
                return PlayerAction.CALL, 0

        # Bluffing opportunity?
        # If no one has bet, take a stab at the pot
        if game_state.current_bet == 0 and PlayerAction.RAISE in legal_actions:
            bluff_raise = min(game_state.pot // 2, max_bet)
            bluff_raise = max(bluff_raise, min_bet)
            if random.random() < 0.25: # Bluff 25% of the time
                return PlayerAction.RAISE, bluff_raise

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
        ranks = sorted(list(set(card.rank.value for card in all_cards)))
        for i in range(len(ranks) - 3):
            if ranks[i+3] - ranks[i] == 3 and len(ranks) >=4 :
                return True
            if set(ranks).issuperset({2,3,4,5}) or set(ranks).issuperset({14,2,3,4}):
                 return True
        return False
    
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