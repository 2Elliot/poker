"""
Flask API Server for Poker Tournament
Updated with security, authentication, and bot approval system
"""
from flask import Flask, jsonify, request, Response, render_template, session, redirect, url_for
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import json
import logging
import sys
import os
from queue import Queue
from threading import Thread, Lock
import time
from datetime import timedelta

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.tournament_runner import TournamentRunner, TournamentSettings, TournamentType
from backend.bot_manager import BotManager
from backend.engine.poker_game import PokerGame, PlayerAction
from backend.tournament import PokerTournament

# Import new security systems
from secure_admin_auth import AdminAuthSystem, User, admin_required
from bot_approval_system import BotReviewSystem
from secure_bot_storage import SecureBotStorage

app = Flask(__name__)
CORS(app)

# Security configuration
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(32))
app.config['SESSION_COOKIE_SECURE'] = False  # Set True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login" # type: ignore

# Initialize systems
auth_system = AdminAuthSystem()
review_system = BotReviewSystem()
bot_storage = SecureBotStorage()

# Master password for running tournaments (should be in env variable)
MASTER_PASSWORD = os.environ.get('MASTER_PASSWORD', 'change-this-in-production-123')

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

# Custom log handler
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


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login user loader"""
    data = auth_system._load_auth_data()
    if user_id in data["admins"]:
        return User(user_id, user_id, is_admin=True)
    return None


# ============================================================================
# PUBLIC ROUTES - Bot submission and viewing
# ============================================================================

@app.route('/')
def index():
    """Main landing page - bot submission"""
    return render_template('submit.html')


@app.route('/tournament')
def tournament_page():
    """Tournament visualization page"""
    return render_template('tournament.html')


@app.route('/api/bots', methods=['GET'])
def get_available_bots():
    """Get list of APPROVED bots available for tournaments"""
    try:
        # Get only approved bots from storage
        approved_bots = bot_storage.list_bots()
        
        bots_info = []
        for bot in approved_bots:
            bots_info.append({
                'id': bot['name'],
                'name': bot['name'],
                'type': 'Approved Bot',
                'wins': bot.get('wins', 0),
                'total_games': bot.get('total_games', 0),
                'win_rate': bot.get('win_rate', 0)
            })
        
        return jsonify({
            'success': True,
            'bots': bots_info
        })
    except Exception as e:
        logging.error(f"Error getting bots: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/bots/submit', methods=['POST'])
def submit_bot():
    """PUBLIC - Submit a bot for review"""
    try:
        data = request.json
        bot_name = data.get('bot_name')
        bot_code = data.get('bot_code')
        submitter_email = data.get('email')
        submitter_password = data.get('password')
        
        if not all([bot_name, bot_code, submitter_email, submitter_password]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
        
        result = review_system.submit_bot(
            bot_name=bot_name,
            bot_code=bot_code,
            submitter_email=submitter_email,
            submitter_password=submitter_password
        )
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error submitting bot: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/bots/my-submissions', methods=['GET'])
def get_my_submissions():
    """PUBLIC - Get user's bot submissions"""
    try:
        email = request.args.get('email')
        if not email:
            return jsonify({
                'success': False,
                'error': 'Email required'
            }), 400
        
        submissions = review_system.get_user_submissions(email)
        return jsonify({
            'success': True,
            'submissions': submissions
        })
        
    except Exception as e:
        logging.error(f"Error getting submissions: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/bots/resubmit/<submission_id>', methods=['POST'])
def resubmit_bot(submission_id):
    """PUBLIC - Resubmit a bot after revision request"""
    try:
        data = request.json
        new_code = data.get('bot_code')
        email = data.get('email')
        
        if not all([new_code, email]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
        
        result = review_system.resubmit_bot(submission_id, new_code, email)
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error resubmitting bot: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/admin/login')
def login_page():
    """Admin login page"""
    if current_user.is_authenticated:
        return redirect(url_for('admin_review_page'))
    return render_template('admin_login.html')


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Admin login endpoint"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    ip = request.remote_addr or '0.0.0.0'
    
    if not username or not password:
        return jsonify({
            "success": False, 
            "error": "Username and password required"
        }), 400
    
    result = auth_system.authenticate(username, password, ip)
    
    if result["success"]:
        login_user(result["user"], remember=True)
        session.permanent = True
        return jsonify({
            "success": True,
            "message": "Login successful",
            "username": username
        })
    else:
        return jsonify(result), 401


@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    """Admin logout endpoint"""
    auth_system._log_audit_event(
        "LOGOUT", 
        current_user.username, 
        request.remote_addr or '0.0.0.0', 
        "User logged out"
    )
    logout_user()
    return jsonify({"success": True, "message": "Logged out successfully"})


@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    """Check if user is authenticated"""
    if current_user.is_authenticated:
        return jsonify({
            "authenticated": True,
            "username": current_user.username,
            "is_admin": current_user.is_admin
        })
    return jsonify({"authenticated": False}), 401


# ============================================================================
# ADMIN ROUTES - Bot Review
# ============================================================================

@app.route('/admin/review')
@login_required
def admin_review_page():
    """Admin review page"""
    if not current_user.is_admin:
        return redirect(url_for('login_page'))
    return render_template('admin_review.html')


@app.route('/api/admin/submissions', methods=['GET'])
@login_required
def get_pending_submissions():
    """ADMIN - Get pending bot submissions"""
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        pending = review_system.get_pending_submissions()
        return jsonify({
            "success": True,
            "submissions": pending
        })
    except Exception as e:
        logging.error(f"Error getting submissions: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/admin/approve/<submission_id>', methods=['POST'])
@login_required
def approve_submission(submission_id):
    """ADMIN - Approve a bot submission"""
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        notes = request.json.get('notes', '')
        result = review_system.approve_bot(submission_id, notes)
        
        if result["success"]:
            auth_system._log_audit_event(
                "BOT_APPROVED",
                current_user.username,
                request.remote_addr or '0.0.0.0',
                f"Approved bot submission {submission_id}"
            )
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error approving bot: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/admin/reject/<submission_id>', methods=['POST'])
@login_required
def reject_submission(submission_id):
    """ADMIN - Reject a bot submission"""
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        reason = request.json.get('reason', 'No reason provided')
        result = review_system.reject_bot(submission_id, reason)
        
        if result["success"]:
            auth_system._log_audit_event(
                "BOT_REJECTED",
                current_user.username,
                request.remote_addr or '0.0.0.0',
                f"Rejected bot submission {submission_id}: {reason}"
            )
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error rejecting bot: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/admin/request-revision/<submission_id>', methods=['POST'])
@login_required
def request_revision(submission_id):
    """ADMIN - Request revisions to a bot submission"""
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        feedback = request.json.get('feedback', '')
        result = review_system.request_revision(submission_id, feedback)
        
        if result["success"]:
            auth_system._log_audit_event(
                "REVISION_REQUESTED",
                current_user.username,
                request.remote_addr or '0.0.0.0',
                f"Requested revision for {submission_id}"
            )
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error requesting revision: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/admin/audit-log', methods=['GET'])
@login_required
def get_audit_log():
    """ADMIN - Get security audit log"""
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        limit = request.args.get('limit', 100, type=int)
        log = auth_system.get_audit_log(limit)
        return jsonify({"success": True, "audit_log": log})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# TOURNAMENT ROUTES - Use approved bots only
# ============================================================================

@app.route('/api/tournament/init', methods=['POST'])
def initialize_tournament():
    """Initialize a new tournament with APPROVED bots only"""
    try:
        data = request.json
        selected_bot_names = data.get('bots', [])
        
        if len(selected_bot_names) < 2:
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
            
            # Create bot manager and load approved bots
            from backend.bot_manager import BotWrapper
            bot_manager = BotManager("players", 10.0)
            bot_manager.bots = {}  # Clear default bots
            
            # Load bots from secure storage using master password
            player_names = []
            bot_count = {}
            
            for bot_name in selected_bot_names:
                # Load bot from encrypted storage
                bot_instance = bot_storage.load_bot(bot_name, MASTER_PASSWORD)
                
                if bot_instance is None:
                    logging.warning(f"Failed to load bot: {bot_name}")
                    continue
                
                # Track count for duplicates
                if bot_name not in bot_count:
                    bot_count[bot_name] = 0
                bot_count[bot_name] += 1
                
                # Create unique player name for duplicates
                if bot_count[bot_name] > 1:
                    player_name = f"{bot_name}_{bot_count[bot_name]}"
                    # Create new instance with unique name
                    unique_bot = bot_instance.__class__(player_name)
                else:
                    player_name = bot_name
                    unique_bot = bot_instance
                
                player_names.append(player_name)
                
                # Wrap bot for safety
                bot_wrapper = BotWrapper(player_name, unique_bot, 10.0)
                bot_manager.bots[player_name] = bot_wrapper
            
            if len(player_names) < 2:
                return jsonify({
                    'success': False,
                    'error': 'Failed to load enough bots'
                }), 400
            
            tournament_state['bot_manager'] = bot_manager
            
            # Create tournament
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
            
            # Play one round
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
                    
                    # Set chip counts
                    for player in player_ids:
                        game.player_chips[player] = tournament.player_stats[player].chips
                    
                    # Play hand
                    final_chips = game.play_hand()
                    
                    # Check for disqualified bots
                    for player_id in list(final_chips.keys()):
                        bot = bot_manager.get_bot(player_id)
                        if bot and bot.is_disqualified():
                            final_chips[player_id] = 0
                    
                    # Update tournament
                    for player_id, chips in final_chips.items():
                        tournament.update_player_chips(player_id, chips)
                    
                    tournament.tables[table_id].dealer_button = game.dealer_button
            
            # Advance tournament
            tournament.advance_hand()
            
            # Rebalance if needed
            if tournament.should_rebalance_tables():
                tournament.rebalance_tables()
        
        return jsonify({
            'success': True,
            'complete': tournament.is_tournament_complete(),
            'state': get_tournament_state_dict(tournament)
        })
        
    except Exception as e:
        logging.error(f"Error in step_tournament: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
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
            'cards': [],
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
    print("=" * 60)
    print("🚀 Starting Poker Tournament Server")
    print("=" * 60)
    print(f"API Server: http://localhost:5000")
    print(f"Admin Panel: http://localhost:5000/admin/login")
    print()
    print("⚠️  IMPORTANT: Set MASTER_PASSWORD environment variable!")
    print("   export MASTER_PASSWORD='your-secure-password'")
    print("=" * 60)
    
    app.run(debug=True, port=5000, threaded=True)