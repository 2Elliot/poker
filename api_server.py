"""
Flask API Server for Poker Tournament
Bridges the Python backend with the JavaScript frontend
"""
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import json
import logging
import sys
import os
from queue import Queue
from threading import Thread, Lock
import time

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from tournament_runner import TournamentRunner, TournamentSettings, TournamentType
from bot_manager import BotManager
from engine.poker_game import PokerGame, PlayerAction
from tournament import PokerTournament

app = Flask(__name__)
CORS(app)

# Global state
tournament_state = {
    'runner': None,
    'tournament': None,
    'is_running': False,
    'is_paused': False,
    'current_game': None,
    'bot_manager': None,
    'log_queue': Queue(),
    'settings': None
}

state_lock = Lock()

# Custom log handler to capture logs
class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record):
        log_entry = {
            'timestamp': time.time(),
            'level': record.levelname,
            'message': self.format(record),
            'name': record.name
        }
        self.log_queue.put(log_entry)

# Setup logging
queue_handler = QueueHandler(tournament_state['log_queue'])
queue_handler.setFormatter(logging.Formatter('%(message)s'))
logging.getLogger().addHandler(queue_handler)
logging.getLogger().setLevel(logging.INFO)


@app.route('/api/bots', methods=['GET'])
def get_available_bots():
    """Get list of available bots from the players directory"""
    try:
        bot_manager = BotManager("players", 10.0)
        loaded_bots = bot_manager.load_all_bots()
        
        bots_info = []
        for bot_name in loaded_bots:
            bots_info.append({
                'id': bot_name,
                'name': bot_name.replace('_', ' ').title(),
                'type': 'Python Bot'
            })
        
        return jsonify({
            'success': True,
            'bots': bots_info
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/tournament/init', methods=['POST'])
def initialize_tournament():
    """Initialize a new tournament with selected bots"""
    try:
        data = request.json
        selected_bots = data.get('bots', [])
        
        if len(selected_bots) < 2:
            return jsonify({
                'success': False,
                'error': 'Need at least 2 bots'
            }), 400
        
        with state_lock:
            # Create settings
            settings = TournamentSettings(
                tournament_type=TournamentType.FREEZE_OUT,
                starting_chips=data.get('starting_chips', 1000),
                small_blind=data.get('small_blind', 10),
                big_blind=data.get('big_blind', 20),
                time_limit_per_action=10.0,
                blind_increase_interval=data.get('blind_increase_interval', 10),
                blind_increase_factor=1.5
            )
            
            tournament_state['settings'] = settings
            
            # Load bot manager
            bot_manager = BotManager("players", 10.0)
            bot_manager.load_all_bots()
            
            # Create unique player names for duplicate bots
            player_names = []
            bot_count = {}
            
            for bot_data in selected_bots:
                bot_id = bot_data['id']
                display_name = bot_data.get('name', bot_id)
                
                # Track count for duplicates
                if bot_id not in bot_count:
                    bot_count[bot_id] = 0
                bot_count[bot_id] += 1
                
                # Create unique player name
                if bot_count[bot_id] > 1:
                    player_name = f"{bot_id}_{bot_count[bot_id]}"
                else:
                    player_name = bot_id
                
                player_names.append(player_name)
                
                # Clone the bot instance for each player
                if bot_id in bot_manager.bots:
                    original_bot = bot_manager.bots[bot_id]
                    # Create a new wrapper with the unique name
                    from bot_manager import BotWrapper
                    
                    # Get the bot class and create a new instance
                    bot_instance = original_bot.bot.__class__(player_name)
                    new_wrapper = BotWrapper(player_name, bot_instance, 10.0)
                    bot_manager.bots[player_name] = new_wrapper
            
            tournament_state['bot_manager'] = bot_manager
            
            # Create tournament with unique player names
            tournament = PokerTournament(player_names, settings)
            tournament_state['tournament'] = tournament
            tournament_state['is_running'] = False
            tournament_state['is_paused'] = False
            
            # Clear log queue
            while not tournament_state['log_queue'].empty():
                tournament_state['log_queue'].get()
        
        return jsonify({
            'success': True,
            'message': f'Tournament initialized with {len(player_names)} bots'
        })
        
    except Exception as e:
        import traceback
        logging.error(f"Error initializing tournament: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/tournament/step', methods=['POST'])
def step_tournament():
    """Execute one hand of the tournament"""
    try:
        with state_lock:
            tournament = tournament_state['tournament']
            bot_manager = tournament_state['bot_manager']
            
            if not tournament:
                return jsonify({
                    'success': False,
                    'error': 'Tournament not initialized'
                }), 400
            
            if tournament.is_tournament_complete():
                return jsonify({
                    'success': True,
                    'complete': True,
                    'state': get_tournament_state_dict(tournament)
                })
            
            # Play one round (one hand per active table)
            active_tables = {tid: table for tid, table in tournament.tables.items() 
                           if len(table.get_active_players()) >= 2}
            
            for table_id, table in active_tables.items():
                player_ids = table.get_active_players()
                if len(player_ids) >= 2:
                    small_blind, big_blind = table.get_current_blinds()
                    
                    bots = {pid: bot_manager.get_bot(pid) for pid in player_ids}
                    
                    game = PokerGame(bots,
                                   starting_chips=0,
                                   small_blind=small_blind,
                                   big_blind=big_blind,
                                   dealer_button_index=table.dealer_button % len(player_ids))
                    
                    # Set chip counts from tournament
                    for player in player_ids:
                        game.player_chips[player] = tournament.player_stats[player].chips
                    
                    # Play the hand
                    final_chips = game.play_hand()
                    
                    # Check for disqualified bots
                    for player_id in list(final_chips.keys()):
                        bot = bot_manager.get_bot(player_id)
                        if bot and bot.is_disqualified():
                            final_chips[player_id] = 0
                    
                    # Update tournament chip counts
                    for player_id, chips in final_chips.items():
                        tournament.update_player_chips(player_id, chips)
                        logging.info(f"Player {player_id} has {chips} chips")
                    
                    tournament.tables[table_id].dealer_button = game.dealer_button
            
            # Advance tournament
            tournament.advance_hand()
            
            # Check for rebalancing
            if tournament.should_rebalance_tables():
                tournament.rebalance_tables()
        
        return jsonify({
            'success': True,
            'complete': tournament.is_tournament_complete(),
            'state': get_tournament_state_dict(tournament)
        })
        
    except Exception as e:
        logging.error(f"Error in step_tournament: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/tournament/state', methods=['GET'])
def get_tournament_state():
    """Get current tournament state"""
    try:
        with state_lock:
            tournament = tournament_state['tournament']
            
            if not tournament:
                return jsonify({
                    'success': False,
                    'error': 'Tournament not initialized'
                }), 400
            
            return jsonify({
                'success': True,
                'state': get_tournament_state_dict(tournament)
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/logs/stream')
def stream_logs():
    """Server-sent events endpoint for streaming logs"""
    def generate():
        while True:
            try:
                log_entry = tournament_state['log_queue'].get(timeout=1)
                yield f"data: {json.dumps(log_entry)}\n\n"
            except:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/tournament/reset', methods=['POST'])
def reset_tournament():
    """Reset the tournament"""
    try:
        with state_lock:
            tournament_state['tournament'] = None
            tournament_state['is_running'] = False
            tournament_state['is_paused'] = False
            tournament_state['current_game'] = None
            
            # Clear logs
            while not tournament_state['log_queue'].empty():
                tournament_state['log_queue'].get()
        
        return jsonify({
            'success': True,
            'message': 'Tournament reset'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def get_tournament_state_dict(tournament):
    """Convert tournament state to dictionary"""
    active_players = tournament.get_active_players()
    
    # Build player data
    players = []
    for i, player_id in enumerate(tournament.players):
        stats = tournament.player_stats[player_id]
        players.append({
            'id': player_id,
            'name': player_id.replace('_', ' ').title(),
            'chips': stats.chips,
            'position': i,
            'isEliminated': stats.is_eliminated,
            'isActive': player_id in active_players,
            'cards': [],  # Cards are hidden in tournament view
            'bet': 0
        })
    
    return {
        'handNumber': tournament.current_hand,
        'totalPlayers': len(tournament.players),
        'activePlayers': len(active_players),
        'eliminatedPlayers': len(tournament.eliminated_players),
        'isComplete': tournament.is_tournament_complete(),
        'players': players,
        'communityCards': [],
        'pot': 0,
        'leaderboard': [
            {'name': name, 'chips': chips, 'position': pos}
            for name, chips, pos in tournament.get_leaderboard()
        ]
    }


if __name__ == '__main__':
    print("Starting Poker Tournament API Server...")
    print("API will be available at http://localhost:5000")
    app.run(debug=True, port=5000, threaded=True)