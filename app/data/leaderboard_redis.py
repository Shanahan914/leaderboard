import redis
from redis.exceptions import RedisError
import logging
from .utils import retry_cache_operation
from .game_redis import CacheError


class LeaderboardRedisCLient:
    ### 0. Initialization ###
    def __init__(self, logger):
        self.r_leaderboard = redis.StrictRedis(host='redis', port=6379, db=0, decode_responses=True)

        self.logger = logger

    # error logging
    def log_and_raise_error(self, message: str):
        self.logger.error("Leaderboard - redis : ", message)
        raise CacheError(message)

    # 1.0  base function for setting score
    def submit_score(self, score, user_id):
        # no error handling as this is not used directly 
        return self.r_leaderboard.zadd(score.game_id, {user_id: score.score})


    ## 1.1 add to score with a retry function ##
    def retry_submit_score(self, score, user_id):
        try:
            return retry_cache_operation(self.submit_score, score, user_id)
        except RedisError as e:
            self.log_and_raise_error(f"Error adding score to sorted set : {e}")


    # 2.0 retrieves the user's rank and score for a single game
    def retrieve_ranking(self, user_id: int, game_id:int):
        # get the rank and score
        try:
            rank = self.r_leaderboard.zrevrank(game_id, user_id)
            score = self.r_leaderboard.zscore(game_id, user_id)
        except RedisError as e:
            self.log_and_raise_error(f"Error retrieving rank or score : {e}")

        # change rank to one index 
        rank_int = int(rank) + 1

        return (rank_int, score)

 
    # 3.1 retrieves the leaderboard for a single game WITH score 
    def retrieve_leaders(self, game_id: int, start : int, end : int):
        try:
            return self.r_leaderboard.zrevrange(game_id, start, end, withscores=True)
        except RedisError as e:
            self.log_and_raise_error(f"Error retrieving leaderboard with score : {e}")

    # 3.2 retrieves the leaderboard for a single game WITHOUT score
    def retrieve_leaders_no_score(self, game_id: int, start : int, end : int):
        try:
            return self.r_leaderboard.zrevrange(game_id, start, end)
        except RedisError as e:
            self.log_and_raise_error(f"Error retrieving leaderboard without score: {e}")

    # 4.0 get user's ranking for all games
    def user_data_all_games(self,user_id : int):
        pass
        # get all game ids from redis
        cursor = 0
        game_keys = []

        try:
        # this scans redis db to get all sorted sets (there is one per game)
            while True:
                cursor, keys = self.r_leaderboard.scan(cursor, match='*', count=1000, _type='zset')
                game_keys.extend(keys)
                if cursor == 0:
                    break
            
            # return None if no game keys found in redis
            if game_keys == []:
                self.logger.warning(f"No game id keys found in redis. User concerned is {user_id}")
                return None 
            
            # create a pipeline to retrieve the user's rankings from each of the games
            pipeline = self.r_leaderboard.pipeline()

            # loop through the games in redis
            for key in game_keys:
                pipeline.zrevrank(key, user_id)

            results = pipeline.execute()

        except RedisError as e:
            self.log_and_raise_error(f"Error retrieving user's ranks for all game : {e}")

        # need to add 1 to be in 1-index format
        results_adjusted = [result + 1 for result in results if result is not None]

        # formatting data
        user_rankings = {key : result for (key, result) in zip(game_keys, results_adjusted)}

        return user_rankings
