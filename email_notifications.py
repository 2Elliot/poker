"""
Email Notification System for Bot Submissions
Sends automated emails for submission, approval, rejection, and revision requests
"""
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging


class EmailNotifier:
    """Handles email notifications for the poker bot system"""
    
    def __init__(self):
        self.enabled = self._check_email_config()
        self.logger = logging.getLogger("email_notifier")
        
        if self.enabled:
            self.smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
            self.smtp_port = int(os.environ.get('SMTP_PORT', '587'))
            self.sender_email = os.environ.get('SENDER_EMAIL')
            self.sender_password = os.environ.get('SENDER_PASSWORD')
            self.site_url = os.environ.get('SITE_URL', 'http://localhost:5000')
            self.logger.info("Email notifications enabled")
        else:
            self.logger.warning("Email notifications disabled - missing configuration")
    
    def _check_email_config(self) -> bool:
        """Check if email is properly configured"""
        required = ['SENDER_EMAIL', 'SENDER_PASSWORD']
        return all(os.environ.get(var) for var in required)
    
    def _send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        """Send an email"""
        if not self.enabled:
            self.logger.info(f"Email disabled - would have sent to {to_email}: {subject}")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = to_email
            
            # Attach HTML body
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            self.logger.info(f"Email sent to {to_email}: {subject}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def notify_submission_received(self, bot_name: str, submitter_email: str, submission_id: str) -> bool:
        """Notify user that their bot was received"""
        subject = f"✓ Bot Submission Received - {bot_name}"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #4a90e2;">🤖 Bot Submission Received</h2>
                
                <p>Hi there!</p>
                
                <p>We've successfully received your poker bot submission:</p>
                
                <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <strong>Bot Name:</strong> {bot_name}<br>
                    <strong>Submission ID:</strong> {submission_id}<br>
                    <strong>Status:</strong> Pending Review
                </div>
                
                <p>Your bot is now in the review queue. Our admin will review it for:</p>
                <ul>
                    <li>Security (no malicious code)</li>
                    <li>Compliance with bot API requirements</li>
                    <li>Code quality and functionality</li>
                </ul>
                
                <p>You'll receive another email once your bot has been reviewed. This typically takes 1-3 days.</p>
                
                <p style="margin-top: 30px;">
                    <a href="{self.site_url}" style="background: #4a90e2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        View Submission Status
                    </a>
                </p>
                
                <p style="color: #666; font-size: 12px; margin-top: 30px;">
                    If you have any questions, feel free to reply to this email.
                </p>
            </div>
        </body>
        </html>
        """
        
        return self._send_email(submitter_email, subject, html_body)
    
    def notify_bot_approved(self, bot_name: str, submitter_email: str, admin_notes: str = "") -> bool:
        """Notify user that their bot was approved"""
        subject = f"🎉 Bot Approved - {bot_name}"
        
        notes_html = ""
        if admin_notes:
            notes_html = f"""
            <div style="background: #e8f5e9; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #4caf50;">
                <strong>Admin Notes:</strong><br>
                {admin_notes}
            </div>
            """
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #4caf50;">🎉 Congratulations! Your Bot is Approved</h2>
                
                <p>Great news!</p>
                
                <p>Your poker bot <strong>{bot_name}</strong> has been reviewed and approved!</p>
                
                {notes_html}
                
                <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <strong>What's Next?</strong>
                    <ul style="margin: 10px 0;">
                        <li>Your bot is now available in tournaments</li>
                        <li>Other users can test against your bot</li>
                        <li>You can watch your bot compete in real-time</li>
                    </ul>
                </div>
                
                <p style="margin-top: 30px;">
                    <a href="{self.site_url}/tournament" style="background: #4caf50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        View Your Bot in Action
                    </a>
                </p>
                
                <p style="color: #666; font-size: 12px; margin-top: 30px;">
                    Good luck in the tournaments! 🏆
                </p>
            </div>
        </body>
        </html>
        """
        
        return self._send_email(submitter_email, subject, html_body)
    
    def notify_bot_rejected(self, bot_name: str, submitter_email: str, reason: str) -> bool:
        """Notify user that their bot was rejected"""
        subject = f"Bot Submission Rejected - {bot_name}"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #d9534f;">Bot Submission Rejected</h2>
                
                <p>Unfortunately, your poker bot <strong>{bot_name}</strong> was not approved.</p>
                
                <div style="background: #ffebee; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #d9534f;">
                    <strong>Reason for Rejection:</strong><br>
                    {reason}
                </div>
                
                <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <strong>What You Can Do:</strong>
                    <ul style="margin: 10px 0;">
                        <li>Review the reason above</li>
                        <li>Fix the issues in your code</li>
                        <li>Submit a new bot with the corrections</li>
                    </ul>
                </div>
                
                <p style="margin-top: 30px;">
                    <a href="{self.site_url}" style="background: #4a90e2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        Submit a New Bot
                    </a>
                </p>
                
                <p style="color: #666; font-size: 12px; margin-top: 30px;">
                    If you have questions about the rejection, feel free to reply to this email.
                </p>
            </div>
        </body>
        </html>
        """
        
        return self._send_email(submitter_email, subject, html_body)
    
    def notify_revision_requested(self, bot_name: str, submitter_email: str, 
                                  feedback: str, submission_id: str) -> bool:
        """Notify user that revisions are needed"""
        subject = f"Revision Requested - {bot_name}"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #f0ad4e;">📝 Revisions Requested for Your Bot</h2>
                
                <p>Your poker bot <strong>{bot_name}</strong> has been reviewed, and we'd like you to make some changes before approval.</p>
                
                <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f0ad4e;">
                    <strong>Requested Changes:</strong><br>
                    {feedback}
                </div>
                
                <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <strong>Next Steps:</strong>
                    <ul style="margin: 10px 0;">
                        <li>Make the requested changes to your code</li>
                        <li>Resubmit your bot using the link below</li>
                        <li>We'll review it again within 1-2 days</li>
                    </ul>
                </div>
                
                <p style="margin-top: 30px;">
                    <a href="{self.site_url}?resubmit={submission_id}" style="background: #4a90e2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        Resubmit Your Bot
                    </a>
                </p>
                
                <p style="color: #666; font-size: 12px; margin-top: 30px;">
                    If you have questions about the requested changes, feel free to reply to this email.
                </p>
            </div>
        </body>
        </html>
        """
        
        return self._send_email(submitter_email, subject, html_body)
    
    def notify_admin_new_submission(self, admin_email: str, bot_name: str, 
                                   submitter_email: str, submission_id: str) -> bool:
        """Notify admin of new submission"""
        if not admin_email:
            return False
        
        subject = f"🆕 New Bot Submission: {bot_name}"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #4a90e2;">New Bot Submission</h2>
                
                <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <strong>Bot Name:</strong> {bot_name}<br>
                    <strong>Submitter:</strong> {submitter_email}<br>
                    <strong>Submission ID:</strong> {submission_id}
                </div>
                
                <p style="margin-top: 30px;">
                    <a href="{self.site_url}/admin/review" style="background: #4a90e2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        Review Now
                    </a>
                </p>
            </div>
        </body>
        </html>
        """
        
        return self._send_email(admin_email, subject, html_body)


# Global instance
email_notifier = EmailNotifier()