import redis
from redis.exceptions import RedisError
import logging
from .utils import retry_cache_operation

class CacheError(Exception):
    """Custom exception for the cache"""
    pass 


class GameRedisCLient:
    ### 0. Initialization ###
    def __init__(self, logger):
        self.r_game = redis.StrictRedis(host='redis', port=6379, db=2, decode_responses=True)

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Optional: Add a console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    # ERROR LOGGING # 
    def log_and_raise_error(self, message: str):
        self.logger.error("Leaderboard - redis : ", message)
        raise CacheError(message)

    ## 1.0 base functions for retry ##
    def set_game_cache(self, game_name : str, id : str):
        return self.r_game.set(id, game_name)
 

    ## 1.1 add to cache with a retry function ##
    def retry_set_game_cache(self, game_name : str, id : str):
        try:
            return retry_cache_operation(self.set_game_cache, game_name, id, self.logger)
        except RedisError as e:
            self.log_and_raise_error(f"Error adding game to cache : {e}")


    ## 2.0 add game to the cache
    def get_game_cache(self, id : str):
        try:
            return self.r_game.get(id)
        except RedisError as e:
            self.log_and_raise_error(f"Error getting game from cache : {e}")
 