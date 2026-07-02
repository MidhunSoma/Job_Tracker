from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from ..services.gmail_service import GmailService
from ..utils.logging import logger

router = APIRouter(prefix="/api/auth", tags=["Google OAuth2 Authentication"])
gmail_service = GmailService()


@router.get("/login")
def login():
    """Redirects the user to the Google OAuth2 authorization page."""
    try:
        auth_url = gmail_service.get_auth_url()
        logger.info("Redirecting user to Google Auth page...", extra={"action": "AUTH_REDIRECT"})
        return RedirectResponse(auth_url)
    except Exception as e:
        logger.exception("OAuth login redirection failed.")
        raise HTTPException(status_code=500, detail=f"Failed to generate authentication URL: {str(e)}")


@router.get("/callback")
def callback(code: str = Query(..., description="Google authorization code")):
    """Handles callback redirect from Google, exchanges code for tokens, and saves them."""
    try:
        gmail_service.save_token(code)
        logger.info("Google OAuth token generated and saved successfully.", extra={"action": "AUTH_CALLBACK_SUCCESS"})
        
        # Return a nice success screen to the user
        html_content = """
        <html>
            <head>
                <title>Authentication Successful</title>
                <style>
                    body {
                        font-family: 'Outfit', sans-serif;
                        background: radial-gradient(circle, #1a1a2e 0%, #16121e 100%);
                        color: #ffffff;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        margin: 0;
                    }
                    .card {
                        background: rgba(255, 255, 255, 0.05);
                        backdrop-filter: blur(10px);
                        border-radius: 16px;
                        padding: 40px;
                        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
                        border: 1px rgba(255, 255, 255, 0.1) solid;
                        text-align: center;
                        max-width: 400px;
                    }
                    h1 {
                        color: #4ade80;
                        margin-bottom: 20px;
                    }
                    p {
                        color: #a78bfa;
                        line-height: 1.6;
                    }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Authentication Successful!</h1>
                    <p>Gmail API credentials have been generated and saved to <code>data/token.json</code>.</p>
                    <p>You can close this tab and return to the Job Tracker Agent dashboard.</p>
                </div>
            </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=200)
    except Exception as e:
        logger.exception("Failed to complete OAuth token exchange callback.")
        raise HTTPException(status_code=500, detail=f"Authentication callback failed: {str(e)}")
