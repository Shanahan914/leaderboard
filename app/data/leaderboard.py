import redis
from api.schema import ScorePublic
import logging
import time


### 0. Initialization ###


## 0.1 logger ##

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s",
                    handlers=[
        logging.StreamHandler(),  # Logs to console
        logging.FileHandler("leaderboard.log")  # Logs to file
    ])

logger = logging.getLogger(__name__)


## 0.2 redis setup ##

# redis setup for all time leaderboard
r_leaderboard = redis.StrictRedis(host='redis', port=6379, db=0, decode_responses=True)

# redis cache for user (id -> username)
r_user = redis.StrictRedis(host='redis', port=6379, db=1, decode_responses=True)

# redis cache for game (id -> name)
r_game = redis.StrictRedis(host='redis', port=6379, db=2, decode_responses=True)


## 0.3 retry base function ##

# generic function to retry an operation -> this will retry if there is a redis set failure
def retry_cache_operation(operation, *args, retries=3, delay=0.5):
    for attempt in range(retries):
        try:
            operation(*args)
            return
        except redis.RedisError as e:
            logger.error(f"Redis error (attempt {attempt + 1}/{retries}): {str(e)}")
            if attempt < retries - 1:
                time.sleep(delay * (2 ** attempt))
            else:
                raise e


### 2. SORTED SET for leaderboard ###

# base function - not be used directly
# submits a single score with score.game the name of the set, score.user_id the member and score.score as the score


## 2.1 submit a score ##

# do not use directly
def submit_score(score: ScorePublic, user_id):
    r_leaderboard.zadd(score.game_id, {user_id: score.score})

# to be used
def retry_submit_score(score:ScorePublic, user_id):
    retry_cache_operation(submit_score, score, user_id)


## 2.2 retrieve user's ranking for a game ##

# retrieves the user's rank and score for a single game
def retrieve_ranking(user_id: int, game_id:int):
    rank = r_leaderboard.zrevrank(game_id, user_id) 
    print('raw rank', rank)
    score = r_leaderboard.zscore(game_id, user_id)
    rank_int = int(rank) + 1
    return (rank_int, score)


## 2.3 retrieve leaders for a game ##

# retrieves the leaderboard for a single game
def retrieve_leaders(game_id: int, start : int, end : int):
    return r_leaderboard.zrevrange(game_id, start, end, withscores=True)


# retrieves the leaderboard for a single game
def retrieve_leaders_no_score(game_id: int, start : int, end : int):
    return r_leaderboard.zrevrange(game_id, start, end)



### 3. CACHE for id to name lookup - game and user_id ###


## 3.1 helper functions ##

# base functions for setting cache
def set_user_cache(username : str, id : str):
    return r_user.set(id, username)

def set_game_cache(game_name : str, id : str):
    return r_game.set(id, game_name)



## 3.2 set and get functions for cache ##

def retry_set_user_cache(username : str, id : str):
    retry_cache_operation(set_user_cache, username, id)

def retry_set_game_cache(game_name : str, id : str):
    retry_cache_operation(set_game_cache, game_name, id)

def get_user_cache(id : str):
    return r_user.get(id)

def get_game_cache(id : str):
    return r_game.get(id)

def get_multiple_usernames(list_user_ids):
    pipeline = r_user.pipeline()

    for key in list_user_ids:
        pipeline.get(key)

    results = pipeline.execute()
    return results


def add_multiple_usernames(list_user_data):
    pipeline = r_user.pipeline()

    for item in list_user_data:
        pipeline.set(item[0], item[1])
        
    results = pipeline.execute()
    return results


# 4.0 get users ranking for all games
def user_data_all_games(user_id : int):
    pass
    # get all game ids from redis
    cursor = 0
    game_keys = []

    while True:
        cursor, keys = r_leaderboard.scan(cursor, match='*', count=1000, _type='zset')
        game_keys.extend(keys)
        if cursor == 0:
            break
    
    # return None if no game keys found in redis
    if game_keys == []:
        logger.warning(f"No game id keys found in redis. User concerned is {user_id}")
        return None 
    
    # create a pipeline to retrieve the user's rankings
    pipeline = r_leaderboard.pipeline()

    for key in game_keys:
        pipeline.zrevrank(key, user_id)

    results = pipeline.execute()

    # need to add 1 to get in ordinal complaint format 
    results_adjusted = [result + 1 for result in results if result is not None]

    user_rankings = {key : result for (key, result) in zip(game_keys, results_adjusted)}

    return user_rankings


# 5.0 get leaders for a game

