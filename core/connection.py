"""
SnapTrade Connection Module for AllYouNeedIsWheel
Replaces IBConnection
"""

import logging
import snaptrade_client
from snaptrade_client.rest import ApiException
from config import Config
from core.logging_config import get_logger

# Configure logging
logger = get_logger('autotrader.connection', 'snaptrade')

class SnapTradeConnection:
    """
    Class for managing connection and data retrieval from SnapTrade
    """
    def __init__(self):
        """
        Initialize the SnapTrade connection client
        """
        self.config = Config()
        self.client_id = self.config.get('snaptrade_client_id')
        self.consumer_key = self.config.get('snaptrade_consumer_key')
        self.user_id = self.config.get('snaptrade_user_id')
        self.user_secret = self.config.get('snaptrade_user_secret')
        
        self.snaptrade = None
        self._connected = False

    def connect(self):
        """
        Configure and test the SnapTrade API client
        
        Returns:
            bool: True if successful, False otherwise
        """
        if self._connected and self.snaptrade:
            return True

        if not all([self.client_id, self.consumer_key]):
            logger.error("SnapTrade credentials (client_id, consumer_key) are missing from connection.json")
            return False
            
        try:
            # Initialize the SnapTrade client
            self.snaptrade = snaptrade_client.SnapTrade(
                client_id=self.client_id,
                consumer_key=self.consumer_key,
            )
            
            # Test the connection by checking API status
            api_response = self.snaptrade.api_status.check()
            
            # Correct check for API status
            if not (api_response and api_response.body and api_response.body.get('online') is True):
                logger.error(f"SnapTrade API is not available. Status: {api_response.body}")
                return False

            self._connected = True
            logger.info(f"Successfully connected to SnapTrade API for user {self.user_id}")
            return True
        except ApiException as e:
            logger.error(f"Error connecting to SnapTrade: {e.body}")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during SnapTrade connection: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """
        Disconnect (no action needed for REST API, but kept for compatibility)
        """
        self.snaptrade = None
        self._connected = False
        logger.info("Disconnected from SnapTrade (client instance released)")

    def is_connected(self):
        """
        Check if connected
        """
        return self._connected

    def get_all_accounts(self):
        """
        Get all brokerage accounts for the user
        """
        if not self.is_connected():
            logger.error("Not connected to SnapTrade.")
            return []
            
        try:
            response = self.snaptrade.account_information.list_user_accounts(
                user_id=self.user_id,
                user_secret=self.user_secret
            )
            return response.body # This is a list of account dictionaries
        except ApiException as e:
            logger.error(f"Error getting SnapTrade accounts: {e.body}")
            return []

    def get_user_holdings(self, account_id):
        """
        Get all holdings (balances, stock positions, and option positions) 
        for a specific account.
        """
        if not self.is_connected():
            logger.error("Not connected to SnapTrade.")
            return None
            
        try:
            # This is the single endpoint that gets balances, positions, and option_positions
            response = self.snaptrade.account_information.get_user_holdings(
                user_id=self.user_id,
                user_secret=self.user_secret,
                account_id=account_id
            )
            return response.body # This is a dictionary
        except ApiException as e:
            logger.error(f"Error getting SnapTrade account holdings: {e.body}")
            return None

    # -----------------------------------------------------------------
    # Methods below are for market data and trading.
    # They are not implemented as SnapTrade is portfolio-only for now.
    # -----------------------------------------------------------------

    def get_stock_price(self, symbol):
        logger.warning(f"get_stock_price({symbol}) is not implemented. Use a market data API.")
        return None
            
    def get_option_chain(self, symbol, expiration=None, right='C', target_strike=None, exchange='SMART'):
        logger.warning(f"get_option_chain({symbol}) is not implemented. Use a market data API.")
        return None

