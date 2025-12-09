#!/usr/bin/env python3
"""
Simple tournament launcher script
Makes it easy for students to run tournaments
"""
from tournament_runner import TournamentRunner, TournamentSettings, TournamentType


def main():
    print("🃏 Poker Bot Tournament System 🤖")
    print("=" * 40)
    
    # Create default settings
    settings = TournamentSettings(
        tournament_type=TournamentType.FREEZE_OUT,
        starting_chips=1000,
        small_blind=10,
        big_blind=20,
        time_limit_per_action=10.0,
        blind_increase_interval=10,
        blind_increase_factor=1.5
    )
    
    print("Tournament Settings:")
    print(f"  Starting Chips: {settings.starting_chips:,}")
    print(f"  Blinds: {settings.small_blind}/{settings.big_blind}")
    print(f"  Time Limit: {settings.time_limit_per_action}s per action")
    print(f"  Blind Increases: Every {settings.blind_increase_interval} hands")
    print()
    
    # Create and run tournament
    runner = TournamentRunner(settings, "players", "logs")
    
    try:
        print("Loading bots and starting tournament...")
        results = runner.run_tournament()
        
        print("\n🎉 Tournament Complete! 🎉")
        
    except Exception as e:
        print(f"\n❌ Tournament Error: {str(e)}")
        print("Check the logs directory for more details.")


if __name__ == "__main__":
    main()