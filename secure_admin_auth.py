"""
Secure Admin Authentication System
Multiple layers of security for admin panel access
"""
import hashlib
import secrets
import time
from functools import wraps
from flask import Flask, request, jsonify, session, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import json
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # Generate secure secret key

# Configure session security
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
app.config['SESSION_COOKIE_HTTPONLY'] = True  # No JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)  # Auto-logout

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(UserMixin):
    """User class for admin authentication"""
    def __init__(self, user_id, username, is_admin=False):
        self.id = user_id
        self.username = username
        self.is_admin = is_admin


class AdminAuthSystem:
    """Manages admin authentication with multiple security layers"""
    
    def __init__(self, auth_file: str = "admin_auth.json"):
        self.auth_file = auth_file
        self.rate_limit_storage = {}  # IP -> [timestamps]
        self.failed_attempts = {}  # IP -> count
        self.lockout_until = {}  # IP -> timestamp
        
        # Initialize auth file if doesn't exist
        if not os.path.exists(auth_file):
            self._create_default_admin()
    
    def _create_default_admin(self):
        """Create default admin account on first run"""
        default_password = secrets.token_urlsafe(16)
        
        admin_data = {
            "admins": {
                "admin": {
                    "password_hash": self._hash_password(default_password),
                    "created_at": datetime.now().isoformat(),
                    "last_login": None,
                    "is_active": True
                }
            },
            "sessions": {},
            "audit_log": []
        }
        
        with open(self.auth_file, 'w') as f:
            json.dump(admin_data, f, indent=2)
        
        print("=" * 60)
        print("🔐 ADMIN ACCOUNT CREATED")
        print("=" * 60)
        print(f"Username: admin")
        print(f"Password: {default_password}")
        print("\n⚠️  SAVE THIS PASSWORD - IT WILL NOT BE SHOWN AGAIN!")
        print("=" * 60)
    
    def _hash_password(self, password: str) -> str:
        """Hash password with salt"""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}${pwd_hash.hex()}"
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        try:
            salt, hash_value = password_hash.split('$')
            pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return pwd_hash.hex() == hash_value
        except:
            return False
    
    def _load_auth_data(self) -> dict:
        """Load authentication data"""
        with open(self.auth_file, 'r') as f:
            return json.load(f)
    
    def _save_auth_data(self, data: dict):
        """Save authentication data"""
        with open(self.auth_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _log_audit_event(self, event_type: str, username: str, ip: str, details: str):
        """Log security events"""
        data = self._load_auth_data()
        data["audit_log"].append({
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "username": username,
            "ip": ip,
            "details": details
        })
        # Keep only last 1000 events
        data["audit_log"] = data["audit_log"][-1000:]
        self._save_auth_data(data)
    
    def check_rate_limit(self, ip: str, max_requests: int = 5, window_seconds: int = 60) -> bool:
        """
        Rate limiting to prevent brute force attacks
        Returns True if under limit, False if over
        """
        now = time.time()
        
        # Clean old timestamps
        if ip in self.rate_limit_storage:
            self.rate_limit_storage[ip] = [
                ts for ts in self.rate_limit_storage[ip] 
                if now - ts < window_seconds
            ]
        else:
            self.rate_limit_storage[ip] = []
        
        # Check if over limit
        if len(self.rate_limit_storage[ip]) >= max_requests:
            return False
        
        # Add current request
        self.rate_limit_storage[ip].append(now)
        return True
    
    def is_locked_out(self, ip: str) -> bool:
        """Check if IP is temporarily locked out"""
        if ip in self.lockout_until:
            if time.time() < self.lockout_until[ip]:
                return True
            else:
                # Lockout expired
                del self.lockout_until[ip]
                self.failed_attempts[ip] = 0
        return False
    
    def record_failed_attempt(self, ip: str):
        """Record failed login attempt"""
        self.failed_attempts[ip] = self.failed_attempts.get(ip, 0) + 1
        
        # Lock out after 5 failed attempts for 15 minutes
        if self.failed_attempts[ip] >= 5:
            self.lockout_until[ip] = time.time() + (15 * 60)
    
    def reset_failed_attempts(self, ip: str):
        """Reset failed attempts after successful login"""
        if ip in self.failed_attempts:
            del self.failed_attempts[ip]
    
    def authenticate(self, username: str, password: str, ip: str) -> dict:
        """
        Authenticate admin user
        Returns: {"success": bool, "user": User or None, "error": str}
        """
        # Check rate limit
        if not self.check_rate_limit(ip, max_requests=5, window_seconds=60):
            self._log_audit_event("RATE_LIMIT", username, ip, "Too many requests")
            return {
                "success": False,
                "error": "Too many requests. Please try again in 1 minute."
            }
        
        # Check lockout
        if self.is_locked_out(ip):
            remaining = int(self.lockout_until[ip] - time.time())
            self._log_audit_event("LOCKED_OUT", username, ip, f"Account locked for {remaining}s")
            return {
                "success": False,
                "error": f"Too many failed attempts. Try again in {remaining // 60} minutes."
            }
        
        # Load admin data
        data = self._load_auth_data()
        
        # Check if user exists
        if username not in data["admins"]:
            self.record_failed_attempt(ip)
            self._log_audit_event("LOGIN_FAIL", username, ip, "Invalid username")
            return {"success": False, "error": "Invalid credentials"}
        
        admin = data["admins"][username]
        
        # Check if account is active
        if not admin.get("is_active", True):
            self._log_audit_event("LOGIN_FAIL", username, ip, "Account disabled")
            return {"success": False, "error": "Account is disabled"}
        
        # Verify password
        if not self._verify_password(password, admin["password_hash"]):
            self.record_failed_attempt(ip)
            self._log_audit_event("LOGIN_FAIL", username, ip, "Invalid password")
            return {"success": False, "error": "Invalid credentials"}
        
        # Success!
        self.reset_failed_attempts(ip)
        
        # Update last login
        admin["last_login"] = datetime.now().isoformat()
        self._save_auth_data(data)
        
        self._log_audit_event("LOGIN_SUCCESS", username, ip, "Successful login")
        
        return {
            "success": True,
            "user": User(username, username, is_admin=True),
            "error": None
        }
    
    def change_password(self, username: str, old_password: str, new_password: str) -> dict:
        """Change admin password"""
        data = self._load_auth_data()
        
        if username not in data["admins"]:
            return {"success": False, "error": "User not found"}
        
        admin = data["admins"][username]
        
        # Verify old password
        if not self._verify_password(old_password, admin["password_hash"]):
            return {"success": False, "error": "Invalid current password"}
        
        # Validate new password strength
        if len(new_password) < 12:
            return {"success": False, "error": "Password must be at least 12 characters"}
        
        # Update password
        admin["password_hash"] = self._hash_password(new_password)
        admin["password_changed_at"] = datetime.now().isoformat()
        self._save_auth_data(data)
        
        self._log_audit_event("PASSWORD_CHANGE", username, "system", "Password changed")
        
        return {"success": True, "message": "Password changed successfully"}
    
    def create_admin(self, username: str, password: str, creator: str) -> dict:
        """Create new admin account"""
        data = self._load_auth_data()
        
        if username in data["admins"]:
            return {"success": False, "error": "Username already exists"}
        
        if len(password) < 12:
            return {"success": False, "error": "Password must be at least 12 characters"}
        
        data["admins"][username] = {
            "password_hash": self._hash_password(password),
            "created_at": datetime.now().isoformat(),
            "created_by": creator,
            "last_login": None,
            "is_active": True
        }
        self._save_auth_data(data)
        
        self._log_audit_event("ADMIN_CREATED", username, "system", f"Created by {creator}")
        
        return {"success": True, "message": f"Admin account '{username}' created"}
    
    def get_audit_log(self, limit: int = 100) -> list:
        """Get recent audit log entries"""
        data = self._load_auth_data()
        return data["audit_log"][-limit:]


# Initialize auth system
auth_system = AdminAuthSystem()


# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    # Load user from auth system
    data = auth_system._load_auth_data()
    if user_id in data["admins"]:
        return User(user_id, user_id, is_admin=True)
    return None


# Decorator for admin-only routes
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function


# Routes
@app.route('/api/auth/login', methods=['POST'])
def login():
    """Admin login endpoint"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    ip = request.remote_addr
    
    if not username or not password:
        return jsonify({"success": False, "error": "Username and password required"}), 400
    
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
    auth_system._log_audit_event("LOGOUT", current_user.username, request.remote_addr, "User logged out")
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


@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def change_password():
    """Change password endpoint"""
    data = request.json
    result = auth_system.change_password(
        current_user.username,
        data.get('old_password'),
        data.get('new_password')
    )
    
    if result["success"]:
        return jsonify(result)
    return jsonify(result), 400


@app.route('/api/admin/audit-log', methods=['GET'])
@admin_required
def get_audit_log():
    """Get audit log (admin only)"""
    limit = request.args.get('limit', 100, type=int)
    log = auth_system.get_audit_log(limit)
    return jsonify({"audit_log": log})


# Protected admin routes example
@app.route('/api/admin/submissions', methods=['GET'])
@admin_required
def get_submissions():
    """Get pending submissions (admin only)"""
    # Your existing review system code
    from bot_approval_system import BotReviewSystem
    review = BotReviewSystem()
    pending = review.get_pending_submissions()
    return jsonify({"submissions": pending})


@app.route('/api/admin/approve/<submission_id>', methods=['POST'])
@admin_required
def approve_submission(submission_id):
    """Approve a bot submission (admin only)"""
    from bot_approval_system import BotReviewSystem
    review = BotReviewSystem()
    
    notes = request.json.get('notes', '')
    result = review.approve_bot(submission_id, notes)
    
    auth_system._log_audit_event(
        "BOT_APPROVED", 
        current_user.username, 
        request.remote_addr, 
        f"Approved bot {submission_id}"
    )
    
    return jsonify(result)


# Additional security: IP whitelist (optional)
ALLOWED_IPS = []  # Add your IP addresses here, e.g., ['192.168.1.100']

def check_ip_whitelist():
    """Check if request is from allowed IP"""
    if not ALLOWED_IPS:  # If empty, allow all
        return True
    return request.remote_addr in ALLOWED_IPS


@app.before_request
def before_request():
    """Run before each request"""
    # Check IP whitelist for admin routes
    if request.path.startswith('/api/admin/') or request.path.startswith('/admin/'):
        if not check_ip_whitelist():
            return jsonify({"error": "Access denied"}), 403


if __name__ == '__main__':
    print("\n🚀 Starting secure admin server...")
    print("=" * 60)
    
    # IMPORTANT: Use HTTPS in production!
    # For development only:
    app.run(host='127.0.0.1', port=5000, debug=False)
    
    # For production with HTTPS:
    # app.run(
    #     host='0.0.0.0',
    #     port=443,
    #     ssl_context=('cert.pem', 'key.pem'),
    #     debug=False
    # )