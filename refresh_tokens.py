import os
import base64
import requests
from loguru import logger
from config import SCWAB_APP_KEY, SCWAB_APP_SECRET
from token_storage import get_refresh_token, save_tokens


def refresh_tokens():
    logger.info("Initializing token refresh...")

    app_key = SCWAB_APP_KEY
    app_secret = SCWAB_APP_SECRET

    # Get refresh token from secure storage
    refresh_token_value = get_refresh_token()
    if not refresh_token_value:
        logger.error("No refresh token found in storage. Please run get_OG_tokens.py first.")
        return None

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token_value,
    }
    headers = {
        "Authorization": f'Basic {base64.b64encode(f"{app_key}:{app_secret}".encode()).decode()}',
        "Content-Type": "application/x-www-form-urlencoded",
    }

    refresh_token_response = requests.post(
        url="https://api.schwabapi.com/v1/oauth/token",
        headers=headers,
        data=payload,
    )
    if refresh_token_response.status_code == 200:
        logger.info("Retrieved new tokens successfully using refresh token.")
    else:
        logger.error(
            f"Error refreshing access token: {refresh_token_response.status_code} - {refresh_token_response.text}"
        )
        return None

    refresh_token_dict = refresh_token_response.json()

    logger.debug(refresh_token_dict)

    # Save the new tokens to secure storage
    if save_tokens(refresh_token_dict):
        logger.info("New tokens saved successfully")
    else:
        logger.error("Failed to save new tokens")
        return None

    logger.info("Token refresh completed successfully.")
    return refresh_token_dict

if __name__ == "__main__":
  refresh_tokens()