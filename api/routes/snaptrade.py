"""
SnapTrade API routes for authentication
"""

import logging
import traceback
from flask import Blueprint, jsonify
import snaptrade_client
from snaptrade_client.rest import ApiException
from config import Config
from core.logging_config import get_logger
from urllib.parse import urlencode # Import urlencode

logger = get_logger('api.routes.snaptrade', 'snaptrade')
bp = Blueprint('snaptrade', __name__, url_prefix='/api/snaptrade')

@bp.route('/connect-broker-url', methods=['GET'])
def get_connect_broker_url():
    """
    Get a redirect URL to connect a new brokerage account
    for the user specified in the config.
    """
    try:
        config = Config()
        client_id = config.get('snaptrade_client_id')
        consumer_key = config.get('snaptrade_consumer_key')
        user_id = config.get('snaptrade_user_id')
        user_secret = config.get('snaptrade_user_secret')
        app_base_url = config.get('app_base_url', 'http://localhost:6001') # Use the URL you access the app from

        if not all([client_id, consumer_key, user_id]):
            logger.error("SnapTrade client_id, consumer_key, or user_id is missing from config.")
            return jsonify({"error": "Server is not configured for SnapTrade."}), 500

        # Initialize the SnapTrade client
        snaptrade = snaptrade_client.SnapTrade(
            client_id=client_id,
            consumer_key=consumer_key,
        )

        # 1. Register the user if they don't exist.
        if not user_secret:
            logger.info(f"No user_secret found. Attempting to register user {user_id}...")
            try:
                # FIX: Pass user_id directly, not as 'registration_data'
                register_response = snaptrade.authentication.register_snap_trade_user(
                    user_id=user_id
                )
                user_secret = register_response.body['user_secret']
                
                # Save the new user_secret back to the config file
                logger.info(f"New user {user_id} registered. Saving user_secret.")
                config.set('snaptrade_user_secret', user_secret)
                config.save_to_file('connection.json') # Save back to the file
                
            except ApiException as e:
                # FIX: Gracefully handle "user already exists" error
                if e.body and "already exist" in str(e.body):
                    logger.info(f"User {user_id} already exists. Proceeding to login.")
                    # This is not an error, we can proceed.
                    # We still need the user_secret from the config.
                    user_secret = config.get('snaptrade_user_secret')
                    if not user_secret:
                        logger.error("User already exists but no user_secret is in connection.json. Please clear user in SnapTrade dashboard.")
                        return jsonify({"error": "User exists but server has no user_secret."}), 500
                else:
                    # A different API error occurred
                    logger.error(f"Error registering SnapTrade user: {e.body}")
                    logger.error(traceback.format_exc())
                    return jsonify({"error": f"SnapTrade API error: {e.body}"}), 500
            except Exception as e:
                logger.error(f"Unexpected error during user registration: {e}")
                logger.error(traceback.format_exc())
                return jsonify({"error": str(e)}), 500
        else:
            logger.info(f"User {user_id} and user_secret already found in config.")

        # 2. Get the login redirect URL for this user
        logger.info(f"Getting login link for user {user_id}...")
        try:
            # FIX: Removed the invalid 'redirect=app_base_url' keyword argument
            api_response = snaptrade.authentication.login_snap_trade_user(
                user_id=user_id,
                user_secret=user_secret
            )
            
            login_url = api_response.body['redirectURI']
            
            # FIX: Manually add the redirect param to the URL.
            # SnapTrade docs show it's a query param on the redirectURI.
            redirect_params = urlencode({'redirect': app_base_url})
            login_url_with_redirect = f"{login_url}&{redirect_params}"
            
            logger.info(f"Successfully got login URL: {login_url_with_redirect}")
            return jsonify({"login_url": login_url_with_redirect})
            
        except ApiException as e:
            logger.error(f"SnapTrade API error while logging in: {e.body}")
            logger.error(traceback.format_exc())
            return jsonify({"error": f"SnapTrade API error: {e.body}"}), 500
        
    except Exception as e:
        logger.error(f"Unexpected error getting SnapTrade login URL: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@bp.route('/disconnect-broker', methods=['POST'])
def disconnect_broker():
    """
    Disconnects all brokerage accounts for the user.
    """
    logger.info("Disconnect broker request received.")
    try:
        config = Config()
        client_id = config.get('snaptrade_client_id')
        consumer_key = config.get('snaptrade_consumer_key')
        user_id = config.get('snaptrade_user_id')
        user_secret = config.get('snaptrade_user_secret')

        if not all([client_id, consumer_key, user_id, user_secret]):
            logger.error("SnapTrade credentials missing for disconnect.")
            return jsonify({"error": "Server is not configured for SnapTrade."}), 500

        # Initialize the SnapTrade client
        snaptrade = snaptrade_client.SnapTrade(
            client_id=client_id,
            consumer_key=consumer_key,
        )

        # 1. Get all brokerage connections (authorizations)
        logger.info(f"Listing brokerage authorizations for user {user_id}...")
        auth_response = snaptrade.connections.list_brokerage_authorizations(
            user_id=user_id,
            user_secret=user_secret
        )
        
        connections = auth_response.body
        if not connections:
            logger.warning("No active brokerage connections found to disconnect.")
            return jsonify({"success": True, "message": "No active connections found."})

        # 2. Loop through and delete each connection
        deleted_connections = []
        for conn in connections:
            conn_id = conn['id']
            logger.warning(f"Disconnecting brokerage connection: {conn_id}")
            
            try:
                # FIX: Correct method is remove_brokerage_authorization
                snaptrade.connections.remove_brokerage_authorization(
                    authorization_id=conn_id,
                    user_id=user_id,
                    user_secret=user_secret
                )
                deleted_connections.append(conn_id)
            except ApiException as e:
                logger.error(f"Failed to delete connection {conn_id}: {e.body}")
                # Continue trying to delete others
            
        logger.info(f"Successfully disconnected {len(deleted_connections)} brokerage(s).")
        return jsonify({
            "success": True, 
            "message": f"Successfully disconnected {len(deleted_connections)} account(s)."
        })
        
    except ApiException as e:
        logger.error(f"SnapTrade API error during disconnect: {e.body}")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"SnapTrade API error: {e.body}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error during disconnect: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

