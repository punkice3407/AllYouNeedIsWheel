import os
import json
import logging

logger = logging.getLogger('autotrader.config')

class Config:
    """
    Configuration class for the AutoTrader application
    """
    
    def __init__(self, default_config=None, config_file=None):
        """
        Initialize the configuration with default values and load from a file if provided
        
        Args:
            default_config (dict, optional): Default configuration values. Defaults to None.
            config_file (str, optional): Path to a JSON configuration file. Defaults to None.
        """
        # Initialize with default values
        self.config = default_config.copy() if default_config else {}
        self.config_file_path = None # Store the path
        
        # If config_file is not provided, check environment variable
        if config_file is None:
            env_config_file = os.environ.get('CONNECTION_CONFIG', 'connection.json')
            if os.path.exists(env_config_file):
                config_file = env_config_file
                logger.info(f"Using connection config from environment: {env_config_file}")
        
        # Load from file if provided
        if config_file and os.path.exists(config_file):
            self.config_file_path = config_file # Save the path
            self.load_from_file(config_file)
            logger.info(f"Configuration loaded from: {config_file}")
        else:
            logger.warning(f"Config file not found: {config_file}")
            
    def load_from_file(self, config_file):
        """
        Load configuration from a JSON file
        
        Args:
            config_file (str): Path to a JSON configuration file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                
            # Update our configuration with values from the file
            self.config.update(file_config)
            self.config_file_path = config_file # Store the path
            return True
        except Exception as e:
            logger.error(f"Error loading configuration from {config_file}: {str(e)}")
            return False
            
    def get(self, key, default=None):
        """
        Get a configuration value
        
        Args:
            key (str): Configuration key
            default: Default value to return if the key is not found
            
        Returns:
            The configuration value or default
        """
        return self.config.get(key, default)
        
    def set(self, key, value):
        """
        Set a configuration value in memory
        
        Args:
            key (str): Configuration key
            value: Value to set
        """
        self.config[key] = value
        
    def to_dict(self):
        """
        Get the entire configuration as a dictionary
        
        Returns:
            dict: Configuration dictionary
        """
        return self.config.copy()
        
    def save_to_file(self):
        """
        Save the current configuration back to the file it was loaded from
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.config_file_path:
            logger.error("Cannot save config: config_file_path is not set.")
            return False
            
        try:
            with open(self.config_file_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Successfully saved config to {self.config_file_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration to {self.config_file_path}: {str(e)}")
            return False
