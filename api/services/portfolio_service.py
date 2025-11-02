"""
Portfolio Service module (api/services/portfolio_service.py)
Manages portfolio data and calculations using SnapTrade
"""

import logging
import time
import traceback
from core.connection import SnapTradeConnection
from config import Config
from datetime import datetime, timedelta

logger = logging.getLogger('api.services.portfolio')

class PortfolioService:
    """
    Service for handling portfolio operations via SnapTrade
    """
    def __init__(self):
        self.config = Config()
        self.logger = logger
        self.logger.info(f"Portfolio service initializing with SnapTrade")
        self.connection = SnapTradeConnection()
        self.primary_account_id = None
        
        # Cache to prevent hitting the API on every single dashboard call
        self.holdings_cache = None
        self.cache_time = None
        self.CACHE_DURATION = 60  # Cache for 60 seconds
        
    def _ensure_connection(self):
        """
        Ensure that the SnapTrade connection exists and is connected
        """
        try:
            if self.connection is None or not self.connection.is_connected():
                self.logger.info("Connecting to SnapTrade...")
                if not self.connection.connect():
                    self.logger.error("Failed to connect to SnapTrade")
                    return False
            return True
        except Exception as e:
            self.logger.error(f"Error ensuring SnapTrade connection: {str(e)}")
            return False
            
    def _get_primary_account_id(self):
        """
        Get the first available brokerage account ID for the user
        """
        if self.primary_account_id:
            return self.primary_account_id
            
        if not self._ensure_connection():
            return None
            
        try:
            accounts = self.connection.get_all_accounts()
            # The response is a list of dictionaries
            if accounts and len(accounts) > 0:
                self.primary_account_id = accounts[0]['id'] # Use dictionary access
                self.logger.info(f"Using SnapTrade account ID: {self.primary_account_id}")
                return self.primary_account_id
            else:
                self.logger.error("No SnapTrade accounts found for this user.")
                return None
        except Exception as e:
            self.logger.error(f"Error getting SnapTrade primary account ID: {e}")
            self.logger.error(traceback.format_exc())
            return None

    def _get_holdings_cache(self):
        """
        Helper to get cached account holdings (which includes balances,
        positions, and option_positions) to reduce API calls.
        """
        current_time = time.time()
        # Check cache
        if self.holdings_cache and self.cache_time and \
           (current_time - self.cache_time) < self.CACHE_DURATION:
            self.logger.debug("Returning cached account holdings")
            return self.holdings_cache

        # Get account ID
        account_id = self._get_primary_account_id()
        if not account_id:
            return None

        # Fetch new data
        self.logger.debug("Fetching fresh account holdings from SnapTrade")
        # This one method gets balances, positions, and option_positions
        holdings = self.connection.get_user_holdings(account_id)
        
        if holdings:
            self.holdings_cache = holdings
            self.cache_time = current_time
            return holdings
        else:
            self.logger.error("Failed to fetch holdings from SnapTrade")
            return None

    def _get_balances(self):
        """
        Gets balances from the cached holdings.
        """
        holdings = self._get_holdings_cache()
        # Check if holdings (a dict) exists and has the 'balances' key
        if holdings and 'balances' in holdings:
            return holdings['balances']
        return None

    def _get_positions(self):
        """
        Gets BOTH stock and option positions from the cached holdings
        and returns them as a single combined list.
        """
        holdings = self._get_holdings_cache()
        if not holdings:
            self.logger.warning("No holdings data available to get positions.")
            return []

        all_positions = []
        
        # 1. Process Stock Positions (from 'positions' array)
        stock_positions = holdings.get('positions', [])
        if stock_positions:
            self.logger.info(f"Processing {len(stock_positions)} stock position(s)")
            for pos in stock_positions:
                try:
                    # Safely parse nested stock symbol data
                    symbol_data = pos.get('symbol', {}).get('symbol', {})
                    if not symbol_data:
                        self.logger.warning(f"Skipping stock position with missing symbol_data: {pos}")
                        continue
                        
                    type_desc = symbol_data.get('type', {}).get('description', 'Unknown')
                    pos_type = "UNKNOWN"
                    if 'Stock' in type_desc:
                        pos_type = 'STK'
                    
                    position_data = {
                        'symbol': symbol_data.get('symbol', 'N/A'),
                        'position': pos.get('units', 0),
                        'market_price': pos.get('price', 0),
                        'market_value': pos.get('units', 0) * pos.get('price', 0),
                        'avg_cost': pos.get('average_purchase_price', 0),
                        'unrealized_pnl': pos.get('open_pnl', 0),
                        'security_type': pos_type
                    }
                    all_positions.append(position_data)
                except Exception as e:
                    self.logger.warning(f"Error processing stock position: {e}")

        # 2. Process Option Positions (from 'option_positions' array)
        option_positions = holdings.get('option_positions', [])
        if option_positions:
            self.logger.info(f"Processing {len(option_positions)} option position(s)")
            for pos in option_positions:
                try:
                    # Parse data based on the structure from your screenshot
                    option_symbol_data = pos.get('symbol', {}).get('option_symbol', {})
                    if not option_symbol_data:
                        self.logger.warning(f"Skipping option position with missing option_symbol data: {pos}")
                        continue

                    # The underlying symbol (e.g., AAPL) is nested inside 'underlying_symbol'
                    underlying_symbol_obj = option_symbol_data.get('underlying_symbol', {})
                    # Use the main 'symbol' field of the underlying_symbol object
                    underlying_symbol = underlying_symbol_obj.get('symbol', 'N/A')
                    
                    if underlying_symbol == 'N/A':
                         self.logger.warning(f"Skipping option position with missing underlying symbol: {pos}")
                         continue

                    position_data = {
                        'symbol': underlying_symbol, # Use the underlying as the main symbol
                        'position': pos.get('units', 0),
                        'market_price': pos.get('price', 0),
                        'market_value': pos.get('units', 0) * pos.get('price', 0),
                        'avg_cost': pos.get('average_purchase_price', 0),
                        'unrealized_pnl': pos.get('open_pnl', 0),
                        'security_type': 'OPT',
                        'expiration': option_symbol_data.get('expiration_date', '').replace('-', ''), # Format as YYYYMMDD
                        'strike': option_symbol_data.get('strike_price', 0),
                        'option_type': option_symbol_data.get('option_type', 'N/A').upper() # 'CALL' or 'PUT'
                    }
                    all_positions.append(position_data)
                except Exception as e:
                    self.logger.warning(f"Error processing option position: {e}")

        self.logger.info(f"Total processed positions (stocks + options): {len(all_positions)}")
        return all_positions

    def get_portfolio_summary(self):
        """
        Get account summary information from SnapTrade and translate it
        """
        try:
            balances_data = self._get_balances() # This now returns a LIST or None
            if balances_data is None:
                self.logger.error("No balances data available for portfolio summary.")
                return None
            
            cash_balance = 0
            account_value = 0
            
            # Iterate over the list of balance objects
            if isinstance(balances_data, list):
                for balance in balances_data:
                    # Safely check for type
                    if balance and balance.get('type') == 'cash' and balance.get('currency', {}).get('code') == 'USD':
                        cash_balance = balance.get('value', 0)
                    
                    if balance and balance.get('type') == 'total' and balance.get('currency', {}).get('code') == 'USD':
                        account_value = balance.get('value', 0)

            if account_value == 0 and cash_balance > 0:
                account_value = cash_balance
            
            initial_margin = 0 
            excess_liquidity = 0
            leverage_percentage = 0
            
            return {
                'account_id': self.primary_account_id,
                'cash_balance': cash_balance,
                'account_value': account_value,
                'excess_liquidity': excess_liquidity,
                'initial_margin': initial_margin,
                'leverage_percentage': leverage_percentage,
                'is_frozen': False
            }
        except Exception as e:
            self.logger.error(f"Error getting portfolio summary from SnapTrade: {e}")
            self.logger.error(traceback.format_exc())
            return None
    
    def get_positions(self, security_type=None):
        """
        Get portfolio positions from SnapTrade, already combined (stocks + options).
        """
        try:
            all_positions = self._get_positions()
            
            if not security_type:
                return all_positions # Return everything
            
            # Filter by security_type if requested
            filtered_list = [pos for pos in all_positions if pos.get('security_type') == security_type]
            return filtered_list
            
        except Exception as e:
            self.logger.error(f"Error in get_positions: {e}")
            self.logger.error(traceback.format_exc())
            return []
    
    def get_weekly_option_income(self):
        """
        Get expected weekly income from option positions expiring this week.
        This method works as-is because it relies on get_positions('OPT').
        """
        try:
            positions = self.get_positions('OPT')
            
            today = datetime.now()
            days_until_friday = (4 - today.weekday()) % 7
            this_friday = today + timedelta(days=days_until_friday)
            this_friday_str = this_friday.strftime('%Y%m%d')
            
            weekly_positions = []
            total_income = 0
            
            for pos in positions:
                if pos.get('position', 0) >= 0:
                    continue
                    
                if pos.get('expiration') and pos.get('expiration') <= this_friday_str:
                    contracts = abs(pos.get('position', 0))
                    premium_per_contract = pos.get('avg_cost', 0)
                    income = premium_per_contract * contracts
                    total_income += income
                    
                    notional_value = None
                    if pos.get('option_type') == 'PUT':
                        strike = pos.get('strike', 0)
                        notional_value = strike * 100 * contracts
                    
                    weekly_positions.append({
                        'symbol': pos.get('symbol', ''),
                        'option_type': pos.get('option_type', ''),
                        'strike': pos.get('strike', 0),
                        'expiration': pos.get('expiration', ''),
                        'position': pos.get('position', 0),
                        'premium_per_contract': premium_per_contract,
                        'avg_cost': premium_per_contract,
                        'income': income,
                        'commission': 0,
                        'notional_value': notional_value
                    })
            
            result = {
                'positions': weekly_positions,
                'total_income': total_income,
                'total_commission': 0,
                'positions_count': len(weekly_positions),
                'this_friday': this_friday.strftime('%Y-%m-%d'),
                'total_put_notional': sum(p.get('notional_value', 0) for p in weekly_positions if p.get('option_type') == 'PUT')
            }
            
            return result
        except Exception as e:
            self.logger.error(f"Error getting weekly option income: {e}")
            self.logger.error(traceback.format_exc())
            return {'positions': [], 'total_income': 0, 'positions_count': 0}

