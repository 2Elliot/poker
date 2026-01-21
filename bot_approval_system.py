"""
Bot Approval and Review System
Allows manual review of bots before they become active in tournaments
"""
import os
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum
from cryptography.fernet import Fernet
import base64


class BotStatus(Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"


class BotReviewSystem:
    """Manages bot submissions, reviews, and approvals"""
    
    def __init__(self, review_directory: str = "bot_reviews", 
                 approved_directory: str = "encrypted_bots"):
        self.review_directory = review_directory
        self.approved_directory = approved_directory
        
        os.makedirs(review_directory, exist_ok=True)
        os.makedirs(approved_directory, exist_ok=True)
        
        self.submissions_file = os.path.join(review_directory, "submissions.json")
        self.submissions = self._load_submissions()
    
    def _load_submissions(self) -> Dict:
        """Load submission metadata"""
        if os.path.exists(self.submissions_file):
            with open(self.submissions_file, 'r') as f:
                return json.load(f)
        return {"submissions": {}, "approved_bots": {}}
    
    def _save_submissions(self):
        """Save submission metadata"""
        with open(self.submissions_file, 'w') as f:
            json.dump(self.submissions, f, indent=2)
    
    def submit_bot(self, bot_name: str, bot_code: str, 
                   submitter_email: str, submitter_password: str) -> Dict:
        """
        Submit a bot for review
        
        Args:
            bot_name: Name for the bot
            bot_code: Python code (plaintext for review)
            submitter_email: Contact email
            submitter_password: Password to encrypt approved version
            
        Returns:
            Submission ID and status
        """
        # Check if bot name is taken
        if bot_name in self.submissions["approved_bots"]:
            return {"success": False, "error": "Bot name already exists"}
        
        # Check if user has pending submissions for this name
        for sub_id, sub in self.submissions["submissions"].items():
            if (sub["bot_name"] == bot_name and 
                sub["submitter_email"] == submitter_email and
                sub["status"] in [BotStatus.PENDING_REVIEW.value, 
                                 BotStatus.REVISION_REQUESTED.value]):
                return {
                    "success": False, 
                    "error": f"You already have a pending submission for '{bot_name}'",
                    "submission_id": sub_id
                }
        
        # Generate submission ID
        submission_id = hashlib.sha256(
            f"{bot_name}{submitter_email}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        # Store bot code in plaintext for review
        code_file = os.path.join(self.review_directory, f"{submission_id}.py")
        with open(code_file, 'w') as f:
            f.write(bot_code)
        
        # Store encrypted password (so admin can encrypt later)
        password_file = os.path.join(self.review_directory, f"{submission_id}.pwd")
        with open(password_file, 'w') as f:
            # Simple encoding (admin will use this to encrypt when approving)
            f.write(base64.b64encode(submitter_password.encode()).decode())
        
        # Create submission record
        self.submissions["submissions"][submission_id] = {
            "bot_name": bot_name,
            "submitter_email": submitter_email,
            "submission_date": datetime.now().isoformat(),
            "status": BotStatus.PENDING_REVIEW.value,
            "code_file": code_file,
            "review_notes": [],
            "revision_count": 0
        }
        self._save_submissions()
        
        # Send notification email to admin (implement this)
        self._notify_admin_new_submission(submission_id, bot_name, submitter_email)
        
        return {
            "success": True,
            "submission_id": submission_id,
            "message": f"Bot '{bot_name}' submitted for review. You'll receive an email when it's reviewed.",
            "status": BotStatus.PENDING_REVIEW.value
        }
    
    def get_pending_submissions(self) -> List[Dict]:
        """Get all submissions pending review (ADMIN ONLY)"""
        pending = []
        for sub_id, sub in self.submissions["submissions"].items():
            if sub["status"] == BotStatus.PENDING_REVIEW.value:
                # Read the code for review
                with open(sub["code_file"], 'r') as f:
                    code = f.read()
                
                # Run automated safety checks
                safety_check = self._run_automated_checks(code)
                
                pending.append({
                    "submission_id": sub_id,
                    "bot_name": sub["bot_name"],
                    "submitter_email": sub["submitter_email"],
                    "submission_date": sub["submission_date"],
                    "code": code,
                    "code_lines": len(code.split('\n')),
                    "safety_check": safety_check,
                    "review_notes": sub["review_notes"]
                })
        
        # Sort by submission date (oldest first)
        pending.sort(key=lambda x: x["submission_date"])
        return pending
    
    def _run_automated_checks(self, code: str) -> Dict:
        """
        Run automated safety checks on bot code
        
        Returns dict with flags for suspicious patterns
        """
        flags = []
        severity = "safe"
        
        # Dangerous imports/functions
        dangerous_patterns = {
            'os.system': 'Command execution (os.system)',
            'subprocess': 'Subprocess execution',
            'eval(': 'Dynamic code evaluation (eval)',
            'exec(': 'Dynamic code execution (exec)',
            '__import__': 'Dynamic imports',
            'open(': 'File operations',
            'requests.': 'Network requests',
            'urllib': 'Network requests',
            'socket': 'Network sockets',
            'pickle': 'Pickle serialization (potential RCE)',
            'os.remove': 'File deletion',
            'os.rmdir': 'Directory deletion',
            'shutil': 'File system operations',
            'sys.exit': 'Program termination',
            '__builtins__': 'Built-ins manipulation',
            'globals()': 'Global scope access',
            'locals()': 'Local scope access',
            'compile(': 'Code compilation',
        }
        
        for pattern, description in dangerous_patterns.items():
            if pattern in code:
                flags.append({
                    "pattern": pattern,
                    "description": description,
                    "severity": "high" if pattern in ['os.system', 'subprocess', 'eval(', 'exec('] else "medium"
                })
                if pattern in ['os.system', 'subprocess', 'eval(', 'exec(']:
                    severity = "dangerous"
                elif severity != "dangerous":
                    severity = "suspicious"
        
        # Check for correct base class
        if 'PokerBotAPI' not in code:
            flags.append({
                "pattern": "Missing PokerBotAPI",
                "description": "Bot doesn't inherit from PokerBotAPI",
                "severity": "high"
            })
            severity = "invalid"
        
        # Check for required methods
        if 'def get_action' not in code:
            flags.append({
                "pattern": "Missing get_action",
                "description": "Required method get_action not found",
                "severity": "high"
            })
            severity = "invalid"
        
        if 'def hand_complete' not in code:
            flags.append({
                "pattern": "Missing hand_complete",
                "description": "Required method hand_complete not found",
                "severity": "high"
            })
            severity = "invalid"
        
        # Check for excessive complexity
        lines = code.split('\n')
        if len(lines) > 500:
            flags.append({
                "pattern": "Large file",
                "description": f"Bot has {len(lines)} lines (unusually large)",
                "severity": "low"
            })
        
        return {
            "severity": severity,
            "flags": flags,
            "total_flags": len(flags),
            "is_safe": severity == "safe"
        }
    
    def approve_bot(self, submission_id: str, admin_notes: str = "") -> Dict:
        """
        Approve a bot submission (ADMIN ONLY)
        Encrypts and moves to approved bots
        """
        if submission_id not in self.submissions["submissions"]:
            return {"success": False, "error": "Submission not found"}
        
        submission = self.submissions["submissions"][submission_id]
        
        # Read the reviewed code
        with open(submission["code_file"], 'r') as f:
            bot_code = f.read()
        
        # Read the submitter's password
        password_file = os.path.join(self.review_directory, f"{submission_id}.pwd")
        with open(password_file, 'r') as f:
            password = base64.b64decode(f.read().encode()).decode()
        
        # Encrypt and store (using the secure storage system)
        from secure_bot_storage import SecureBotStorage
        storage = SecureBotStorage(self.approved_directory)
        
        result = storage.upload_bot(
            submission["bot_name"], 
            bot_code, 
            password
        )
        
        if not result["success"]:
            return result
        
        # Update submission status
        submission["status"] = BotStatus.APPROVED.value
        submission["approval_date"] = datetime.now().isoformat()
        submission["admin_notes"] = admin_notes
        submission["review_notes"].append({
            "date": datetime.now().isoformat(),
            "action": "approved",
            "notes": admin_notes
        })
        
        # Move to approved bots
        self.submissions["approved_bots"][submission["bot_name"]] = {
            "submission_id": submission_id,
            "submitter_email": submission["submitter_email"],
            "approval_date": submission["approval_date"]
        }
        
        self._save_submissions()
        
        # Clean up review files
        self._cleanup_submission_files(submission_id)
        
        # Notify submitter
        self._notify_submitter_approved(
            submission["submitter_email"], 
            submission["bot_name"]
        )
        
        return {
            "success": True,
            "message": f"Bot '{submission['bot_name']}' approved and activated"
        }
    
    def reject_bot(self, submission_id: str, reason: str) -> Dict:
        """Reject a bot submission (ADMIN ONLY)"""
        if submission_id not in self.submissions["submissions"]:
            return {"success": False, "error": "Submission not found"}
        
        submission = self.submissions["submissions"][submission_id]
        
        submission["status"] = BotStatus.REJECTED.value
        submission["rejection_date"] = datetime.now().isoformat()
        submission["rejection_reason"] = reason
        submission["review_notes"].append({
            "date": datetime.now().isoformat(),
            "action": "rejected",
            "notes": reason
        })
        
        self._save_submissions()
        
        # Notify submitter
        self._notify_submitter_rejected(
            submission["submitter_email"],
            submission["bot_name"],
            reason
        )
        
        # Clean up files
        self._cleanup_submission_files(submission_id)
        
        return {
            "success": True,
            "message": "Bot rejected"
        }
    
    def request_revision(self, submission_id: str, feedback: str) -> Dict:
        """Request revisions to a bot submission (ADMIN ONLY)"""
        if submission_id not in self.submissions["submissions"]:
            return {"success": False, "error": "Submission not found"}
        
        submission = self.submissions["submissions"][submission_id]
        
        submission["status"] = BotStatus.REVISION_REQUESTED.value
        submission["revision_count"] += 1
        submission["review_notes"].append({
            "date": datetime.now().isoformat(),
            "action": "revision_requested",
            "notes": feedback
        })
        
        self._save_submissions()
        
        # Notify submitter with feedback
        self._notify_submitter_revision_needed(
            submission["submitter_email"],
            submission["bot_name"],
            feedback,
            submission_id
        )
        
        return {
            "success": True,
            "message": "Revision requested, submitter notified"
        }
    
    def resubmit_bot(self, submission_id: str, new_code: str, 
                     submitter_email: str) -> Dict:
        """
        User resubmits after revision request
        """
        if submission_id not in self.submissions["submissions"]:
            return {"success": False, "error": "Submission not found"}
        
        submission = self.submissions["submissions"][submission_id]
        
        # Verify it's the same submitter
        if submission["submitter_email"] != submitter_email:
            return {"success": False, "error": "Unauthorized"}
        
        # Check status
        if submission["status"] != BotStatus.REVISION_REQUESTED.value:
            return {"success": False, "error": "This submission is not awaiting revision"}
        
        # Update the code file
        with open(submission["code_file"], 'w') as f:
            f.write(new_code)
        
        # Reset status to pending review
        submission["status"] = BotStatus.PENDING_REVIEW.value
        submission["resubmission_date"] = datetime.now().isoformat()
        submission["review_notes"].append({
            "date": datetime.now().isoformat(),
            "action": "resubmitted",
            "notes": "Code updated by submitter"
        })
        
        self._save_submissions()
        
        # Notify admin
        self._notify_admin_resubmission(submission_id, submission["bot_name"])
        
        return {
            "success": True,
            "message": "Bot resubmitted for review"
        }
    
    def get_user_submissions(self, email: str) -> List[Dict]:
        """Get all submissions for a user"""
        user_subs = []
        for sub_id, sub in self.submissions["submissions"].items():
            if sub["submitter_email"] == email:
                user_subs.append({
                    "submission_id": sub_id,
                    "bot_name": sub["bot_name"],
                    "status": sub["status"],
                    "submission_date": sub["submission_date"],
                    "review_notes": sub["review_notes"],
                    "revision_count": sub.get("revision_count", 0)
                })
        return user_subs
    
    def _cleanup_submission_files(self, submission_id: str):
        """Remove plaintext code files after approval/rejection"""
        files = [
            os.path.join(self.review_directory, f"{submission_id}.py"),
            os.path.join(self.review_directory, f"{submission_id}.pwd")
        ]
        for f in files:
            if os.path.exists(f):
                os.remove(f)
    
    def _notify_admin_new_submission(self, sub_id: str, bot_name: str, email: str):
        """Send notification to admin about new submission"""
        # TODO: Implement email notification
        print(f"[ADMIN NOTIFICATION] New bot submission: {bot_name} from {email}")
        print(f"Review at: /admin/review/{sub_id}")
    
    def _notify_admin_resubmission(self, sub_id: str, bot_name: str):
        """Notify admin about resubmission"""
        print(f"[ADMIN NOTIFICATION] Bot resubmitted: {bot_name}")
        print(f"Review at: /admin/review/{sub_id}")
    
    def _notify_submitter_approved(self, email: str, bot_name: str):
        """Notify submitter their bot was approved"""
        # TODO: Implement email notification
        print(f"[EMAIL to {email}] Your bot '{bot_name}' has been approved!")
    
    def _notify_submitter_rejected(self, email: str, bot_name: str, reason: str):
        """Notify submitter their bot was rejected"""
        print(f"[EMAIL to {email}] Your bot '{bot_name}' was rejected: {reason}")
    
    def _notify_submitter_revision_needed(self, email: str, bot_name: str, 
                                         feedback: str, sub_id: str):
        """Notify submitter that revisions are needed"""
        print(f"[EMAIL to {email}] Your bot '{bot_name}' needs revisions:")
        print(f"Feedback: {feedback}")
        print(f"Resubmit at: /submit/revise/{sub_id}")


# Example Flask routes for admin review interface
"""
from flask import Flask, render_template, request, jsonify, session
from flask_login import login_required, current_user

app = Flask(__name__)
review_system = BotReviewSystem()

@app.route('/api/bots/submit', methods=['POST'])
def submit_bot():
    data = request.json
    result = review_system.submit_bot(
        bot_name=data['bot_name'],
        bot_code=data['bot_code'],
        submitter_email=data['email'],
        submitter_password=data['password']
    )
    return jsonify(result)

@app.route('/api/admin/submissions', methods=['GET'])
@login_required
def get_pending_submissions():
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    
    pending = review_system.get_pending_submissions()
    return jsonify({"submissions": pending})

@app.route('/api/admin/approve/<submission_id>', methods=['POST'])
@login_required
def approve_bot(submission_id):
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    
    notes = request.json.get('notes', '')
    result = review_system.approve_bot(submission_id, notes)
    return jsonify(result)

@app.route('/api/admin/reject/<submission_id>', methods=['POST'])
@login_required
def reject_bot(submission_id):
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    
    reason = request.json.get('reason', 'No reason provided')
    result = review_system.reject_bot(submission_id, reason)
    return jsonify(result)

@app.route('/api/admin/request-revision/<submission_id>', methods=['POST'])
@login_required
def request_revision(submission_id):
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    
    feedback = request.json.get('feedback', '')
    result = review_system.request_revision(submission_id, feedback)
    return jsonify(result)

@app.route('/api/my-submissions', methods=['GET'])
def get_my_submissions():
    email = request.args.get('email')
    submissions = review_system.get_user_submissions(email)
    return jsonify({"submissions": submissions})
"""

if __name__ == "__main__":
    # Example usage
    review = BotReviewSystem()
    
    # User submits a bot
    sample_code = '''
from bot_api import PokerBotAPI, PlayerAction
from engine.poker_game import GameState
from engine.cards import Card
from typing import List

class MyBot(PokerBotAPI):
    def get_action(self, game_state, hole_cards, legal_actions, min_bet, max_bet):
        return PlayerAction.CALL, 0
    
    def hand_complete(self, game_state, hand_result):
        pass
'''
    
    result = review.submit_bot(
        "TestBot",
        sample_code,
        "user@example.com",
        "user_password_123"
    )
    print("Submission result:", result)
    
    # Admin reviews pending submissions
    pending = review.get_pending_submissions()
    print(f"\nPending submissions: {len(pending)}")
    
    if pending:
        sub = pending[0]
        print(f"\nReviewing: {sub['bot_name']}")
        print(f"Safety check: {sub['safety_check']['severity']}")
        print(f"Flags: {sub['safety_check']['total_flags']}")