import redis
from redis.exceptions import RedisError
import logging
from .utils import retry_cache_operation
from .game_redis import CacheError


class UserRedisClient:
    ### 0. Initialization ###
    def __init__(self, logger):
        self.r_user = redis.StrictRedis(host='redis', port=6379, db=1, decode_responses=True)
        self.logger = logger

        # error logging
    def log_and_raise_error(self, message: str):
        self.logger.error("Leaderboard - redis : ", message)
        raise CacheError(message)

    # 1.0 base functions for setting cache
    def set_user_cache(self, username : str, id : str):
        return self.r_user.set(id, username)


    ## 1.1 add to cache with a retry function ##
    def retry_set_user_cache(self, username : str, id : str):
        try:
            return retry_cache_operation(self.set_user_cache, username, id, self.logger)
        except RedisError as e:
            self.log_and_raise_error(f"Error adding user to cache: {e}")

    ## 2.0 get a single username from the cache
    def get_user_cache(self, id : str):
        try:
            return self.r_user.get(id)
        except RedisError as e:
            self.log_and_raise_error(f"Error get user from cache: {e}")
            

    ## 2.1 get multiple usernames from the cache
    def get_multiple_usernames(self, list_user_ids):
        
        try:
        # set up pipeline to fetch data in one operations
            pipeline = self.r_user.pipeline()

            # loop through list of users
            for key in list_user_ids:
                pipeline.get(key)

            # get and return results
            results = pipeline.execute()
            return results
        
        except RedisError as e:
            self.log_and_raise_error(f"Error getting multiple users from cache : {e}")


    ## 2.2 set multiple usernames in the cache
    def add_multiple_usernames(self, list_user_data):
        try:
            pipeline = self.r_user.pipeline()

            for item in list_user_data:
                pipeline.set(item[0], item[1])
                
            results = pipeline.execute()
            return results
        
        except RedisError as e:
            self.log_and_raise_error(f"Error adding multiple users to cache : {e}")




