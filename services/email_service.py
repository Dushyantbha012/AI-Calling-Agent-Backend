import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import datetime
from typing import Optional, List
from logger_config import get_logger

logger = get_logger("EmailService")


class EmailService:
    """
    Email service for sending information and summaries via email
    """
    
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = os.getenv("SENDER_EMAIL")
        self.sender_password = os.getenv("SENDER_PASSWORD")  # App password for Gmail
        self.sender_name = os.getenv("GMAIL_SENDER_NAME", "AI Assistant")
        
        # Validate configuration
        if not self.sender_email or not self.sender_password:
            logger.warning("Email service not configured. Please set SENDER_EMAIL and SENDER_PASSWORD")
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"Email service initialized with sender: {self.sender_email}")

    async def send_email(
        self, 
        to_email: str, 
        subject: str, 
        body: str, 
        is_html: bool = False,
        attachments: Optional[List[dict]] = None
    ) -> bool:
        """
        Send an email
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body content
            is_html: Whether the body is HTML content
            attachments: List of attachments with 'filename' and 'content' keys
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self.enabled:
            logger.error("Email service is not configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add body
            if is_html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            # Add attachments if any
            if attachments:
                for attachment in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment['content'])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment["filename"]}'
                    )
                    msg.attach(part)
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            text = msg.as_string()
            server.sendmail(self.sender_email, to_email, text)
            server.quit()
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    async def send_call_summary(
        self, 
        to_email: str, 
        call_summary: str, 
        call_sid: str,
        phone_number: str,
        include_transcript: bool = False,
        transcript: Optional[List[dict]] = None
    ) -> bool:
        """Send call summary via email"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            subject = f"Call Summary - {timestamp}"
            
            # Create HTML body
            html_body = f"""
            <html>
            <head></head>
            <body>
                <h2>📞 Call Summary</h2>
                <p><strong>Date:</strong> {timestamp}</p>
                <p><strong>Call ID:</strong> {call_sid}</p>
                <p><strong>Phone Number:</strong> {phone_number}</p>
                
                <h3>Summary</h3>
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px;">
                    {call_summary.replace('\\n', '<br>')}
                </div>
            """
            
            if include_transcript and transcript:
                html_body += """
                <h3>Full Conversation Transcript</h3>
                <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px;">
                """
                
                for entry in transcript:
                    role = entry.get('role', 'unknown')
                    content = entry.get('content', '')
                    
                    if role == 'user':
                        html_body += f'<p><strong>👤 You:</strong> {content}</p>'
                    elif role == 'assistant':
                        html_body += f'<p><strong>🤖 Assistant:</strong> {content}</p>'
                
                html_body += "</div>"
            
            html_body += """
                <hr>
                <p style="color: #666; font-size: 12px;">
                    This summary was generated by your AI assistant.
                </p>
            </body>
            </html>
            """
            
            return await self.send_email(to_email, subject, html_body, is_html=True)
            
        except Exception as e:
            logger.error(f"Failed to send call summary email: {str(e)}")
            return False

    async def send_information(
        self, 
        to_email: str, 
        topic: str, 
        information: str
    ) -> bool:
        """Send information via email"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            subject = f"Information: {topic.title()}"
            
            # Create HTML body
            html_body = f"""
            <html>
            <head></head>
            <body>
                <h2>📋 Information Request</h2>
                <p><strong>Topic:</strong> {topic.title()}</p>
                <p><strong>Date:</strong> {timestamp}</p>
                
                <h3>Information</h3>
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px;">
                    {information.replace('\\n', '<br>')}
                </div>
                
                <hr>
                <p style="color: #666; font-size: 12px;">
                    This information was requested during your call with our AI assistant.
                </p>
            </body>
            </html>
            """
            
            return await self.send_email(to_email, subject, html_body, is_html=True)
            
        except Exception as e:
            logger.error(f"Failed to send information email: {str(e)}")
            return False


# Global email service instance
email_service = EmailService()
