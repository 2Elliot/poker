#!/usr/bin/env python3
"""
Test script to verify bots are working correctly
Run this to debug bot behavior
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from bot_manager import BotManager
from engine.poker_game import PokerGame, GameState, PlayerAction
from engine.cards import Card, Rank, Suit

# Test bot loading
print("="*60)
print("TESTING BOT LOADING")
print("="*60)

bot_manager = BotManager("players", 10.0)
loaded_bots = bot_manager.load_all_bots()

print(f"\nLoaded {len(loaded_bots)} bots:")
for bot_name in loaded_bots:
    print(f"  - {bot_name}")

# Test creating duplicate instances
print("\n" + "="*60)
print("TESTING DUPLICATE BOT INSTANCES")
print("="*60)

if loaded_bots:
    test_bot_id = loaded_bots[0]
    print(f"\nCreating 3 instances of: {test_bot_id}")
    
    instances = []
    for i in range(1, 4):
        bot_name = f"{test_bot_id}_{i}"
        
        # Get original bot
        original_wrapper = bot_manager.bots[test_bot_id]
        bot_class = original_wrapper.bot.__class__
        
        # Create new instance
        new_instance = bot_class(bot_name)
        from bot_manager import BotWrapper
        new_wrapper = BotWrapper(bot_name, new_instance, 10.0)
        
        bot_manager.bots[bot_name] = new_wrapper
        instances.append(bot_name)
        print(f"  ✓ Created: {bot_name}")
    
    # Test bot behavior
    print("\n" + "="*60)
    print("TESTING BOT DECISION MAKING")
    print("="*60)
    
    for bot_name in instances[:2]:  # Test first 2 instances
        print(f"\nTesting: {bot_name}")
        wrapper = bot_manager.bots[bot_name]
        
        # Create a test game state
        test_state = GameState(
            pot=100,
            community_cards=[],
            current_bet=20,
            player_chips={bot_name: 1000, "opponent": 1000},
            player_bets={bot_name: 0, "opponent": 20},
            active_players=[bot_name, "opponent"],
            current_player=bot_name,
            round_name="preflop",
            min_bet=40,
            min_raise=20,
            big_blind=20,
            small_blind=10
        )
        
        # Create test hole cards
        hole_cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.KING, Suit.SPADES)
        ]
        
        # Get legal actions - USE ACTUAL ENUM VALUES, NOT STRINGS!
        from engine.poker_game import PlayerAction
        legal_actions = [PlayerAction.FOLD, PlayerAction.CALL, PlayerAction.RAISE, PlayerAction.ALL_IN]
        
        print(f"  Game State:")
        print(f"    - Pot: ${test_state.pot}")
        print(f"    - Current bet: ${test_state.current_bet}")
        print(f"    - Player's bet: ${test_state.player_bets[bot_name]}")
        print(f"    - To call: ${test_state.current_bet - test_state.player_bets[bot_name]}")
        print(f"    - Hole cards: {hole_cards}")
        print(f"    - Legal actions: {[a.name for a in legal_actions]}")
        print(f"    - Legal actions types: {[type(a) for a in legal_actions]}")
        
        # Get bot's action
        try:
            action, amount = wrapper.get_action(
                test_state,
                hole_cards,
                legal_actions,
                min_bet=40,
                max_bet=1000
            )
            
            print(f"  Bot's decision:")
            print(f"    - Action: {action.name}")
            print(f"    - Action type: {type(action)}")
            print(f"    - Amount: ${amount}")
            
            # Validate action
            if action in legal_actions:
                print(f"    ✓ Action is legal")
            else:
                print(f"    ✗ Action is ILLEGAL! Not in legal_actions")
                print(f"    Action: {action}, type: {type(action)}")
                print(f"    Legal: {legal_actions}, types: {[type(a) for a in legal_actions]}")
                
        except Exception as e:
            print(f"  ✗ Error getting action: {str(e)}")
            import traceback
            traceback.print_exc()

    # Test a simple 2-player game
    print("\n" + "="*60)
    print("TESTING FULL GAME")
    print("="*60)
    
    if len(instances) >= 2:
        print(f"\nPlaying game between: {instances[0]} vs {instances[1]}")
        
        game_bots = {
            instances[0]: bot_manager.get_bot(instances[0]),
            instances[1]: bot_manager.get_bot(instances[1])
        }
        
        try:
            game = PokerGame(
                game_bots,
                starting_chips=1000,
                small_blind=10,
                big_blind=20,
                dealer_button_index=0
            )
            
            print("Starting hand...")
            final_chips = game.play_hand()
            
            print("\nHand complete!")
            print("Final chip counts:")
            for player, chips in final_chips.items():
                print(f"  {player}: ${chips}")
                
        except Exception as e:
            print(f"\n✗ Error during game: {str(e)}")
            import traceback
            traceback.print_exc()

print("\n" + "="*60)
print("TESTING COMPLETE")
print("="*60)