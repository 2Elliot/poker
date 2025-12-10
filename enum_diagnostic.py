#!/usr/bin/env python3
"""
Diagnostic script to find enum comparison issue
"""
import sys
import os

# Import PlayerAction from different places
from engine.poker_game import PlayerAction as PA_Game
from bot_api import PlayerAction as PA_BotAPI

print("="*60)
print("ENUM COMPARISON DIAGNOSTIC")
print("="*60)

# Check if they're the same class
print(f"\nPlayerAction from poker_game: {PA_Game}")
print(f"PlayerAction from bot_api: {PA_BotAPI}")
print(f"Are they the same class? {PA_Game is PA_BotAPI}")

# Create instances
fold_game = PA_Game.FOLD
fold_api = PA_BotAPI.FOLD

print(f"\nFOLD from poker_game: {fold_game}")
print(f"FOLD from bot_api: {fold_api}")
print(f"Are they equal (==)? {fold_game == fold_api}")
print(f"Are they identical (is)? {fold_game is fold_api}")

# Test list membership
legal_actions_game = [PA_Game.FOLD, PA_Game.CALL, PA_Game.RAISE]
legal_actions_api = [PA_BotAPI.FOLD, PA_BotAPI.CALL, PA_BotAPI.RAISE]

print(f"\nTesting 'in' operator:")
print(f"PA_Game.FOLD in legal_actions_game: {PA_Game.FOLD in legal_actions_game}")
print(f"PA_Game.FOLD in legal_actions_api: {PA_Game.FOLD in legal_actions_api}")
print(f"PA_BotAPI.FOLD in legal_actions_game: {PA_BotAPI.FOLD in legal_actions_game}")
print(f"PA_BotAPI.FOLD in legal_actions_api: {PA_BotAPI.FOLD in legal_actions_api}")

# Check IDs
print(f"\nObject IDs:")
print(f"id(PA_Game): {id(PA_Game)}")
print(f"id(PA_BotAPI): {id(PA_BotAPI)}")
print(f"id(PA_Game.FOLD): {id(PA_Game.FOLD)}")
print(f"id(PA_BotAPI.FOLD): {id(PA_BotAPI.FOLD)}")

# The real test - what bot_manager sees
print("\n" + "="*60)
print("SIMULATING BOT_MANAGER SCENARIO")
print("="*60)

from bot_manager import BotManager
from engine.poker_game import GameState, PlayerAction
from engine.cards import Card, Rank, Suit

# Load a bot
bot_manager = BotManager("players", 10.0)
bot_manager.load_all_bots()

if bot_manager.bots:
    bot_name = list(bot_manager.bots.keys())[0]
    wrapper = bot_manager.bots[bot_name]
    
    # Create test state
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
    
    hole_cards = [Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.SPADES)]
    legal_actions = [PlayerAction.FOLD, PlayerAction.CALL, PlayerAction.RAISE, PlayerAction.ALL_IN]
    
    print(f"\nCalling bot's get_action...")
    print(f"legal_actions passed to bot: {legal_actions}")
    print(f"legal_actions types: {[type(a) for a in legal_actions]}")
    print(f"legal_actions module: {[a.__class__.__module__ for a in legal_actions]}")
    
    # Get action directly from bot (bypass wrapper)
    action, amount = wrapper.bot.get_action(test_state, hole_cards, legal_actions, 40, 1000)
    
    print(f"\nBot returned:")
    print(f"  action: {action}")
    print(f"  action type: {type(action)}")
    print(f"  action module: {action.__class__.__module__}")
    print(f"  action in legal_actions: {action in legal_actions}")
    
    # Check each legal action individually
    print(f"\nChecking action against each legal action:")
    for legal in legal_actions:
        print(f"  {action} == {legal}: {action == legal}")
        print(f"  {action} is {legal}: {action is legal}")
        print(f"  id({action}): {id(action)}, id({legal}): {id(legal)}")

print("\n" + "="*60)
print("DIAGNOSTIC COMPLETE")
print("="*60)