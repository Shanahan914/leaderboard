
from .game_redis import GameRedisCLient, CacheError
from .postgres import PostgresClient, DBError
from .user_redis import UserRedisClient
from .leaderboard_redis import LeaderboardRedisCLient
from api.database import SessionDep
from api.schema import UserInput, GameIDInput
from typing import List 
import logging


class DataServiceException(Exception):
    ''' Custom exception for DataService. '''
    pass


class DataService:

    def __init__(self, session : SessionDep, logger):
        self.game_redis = GameRedisCLient(logger)
        self.user_redis = UserRedisClient(logger)
        self.leaderboard_redis = LeaderboardRedisCLient(logger)
        self.postgresClient = PostgresClient(session, logger)

        self.logger = logger

    # add user to the cache 
    def set_user_cache(self, username : str, id : str):
        return self.user_redis.retry_set_user_cache(username, id)
    
    # add multiple users to the cache
    def set_multiple_usernames(self, list_user_data):
        return self.user_redis.add_multiple_usernames(list_user_data)
    
    # get a single username from the cache 
    def get_single_username(self, id : str):
        return self.user_redis.get_user_cache(id)
    
    # get multiple usernames from the cache 
    def get_mutiple_usernames(self, list_user_ids):
        return self.user_redis.get_multiple_usernames(list_user_ids)
    
    # add a game to the cache 
    def add_game_cache(self, game_name: str, id : str):
        return self.game_redis.retry_set_game_cache(game_name, id)
    
    # get game from the cache 
    def get_game_cache(self, id : str):
        return self.game_redis.get_game_cache(id)
        
    # create a new user in db
    def add_user(self, user : UserInput):
        try:
            return self.postgresClient.add_user(user)
        except DBError as e:
            raise DataServiceException(e)
    
    # get multiple users
    def get_multiple_users(self, list_of_ids):
        return self.postgresClient.retrieve_multiple_usernames_pg(list_of_ids)
    
    # Get top player info
    def get_player_info(self, leaders : List[str]):
        return self.postgresClient.get_player_info(leaders)
    
    # get list of games from postgres
    def get_list_games(self):
        return self.postgresClient.get_games()
    
    # Add game to postgres and redis
    def add_game(self, game: GameIDInput):
        # add to postgres. This will raise an exception is unsuccessful
        new_game = self.postgresClient.add_game_pg(game)
        # add to redis. 
        self.add_game_cache(new_game.name, new_game.id)
        return new_game
    
    def get_game_pg(self, game_id):
        return self.postgresClient.get_game_pg(game_id)
    
    # Submit a score
    def submit_score(self, score : int, user_id: int):
        # add to postgres. This wil lraise an exception if unsuccessful
        new_score = self.postgresClient.submit_score(user_id, score)
        # add to redis
        self.leaderboard_redis.retry_submit_score(new_score, user_id)
        return new_score
    
    #  retrieve the user's rank for a single game
    def get_single_ranking(self, user_id : int, game_id: int):
        return self.leaderboard_redis.retrieve_ranking(user_id, game_id)
    
    # retrieve the leaderboard for a single game WITH score
    def get_leaderboard_with_score(self, game_id: int, start : int, end : int):
        return self.leaderboard_redis.retrieve_leaders(game_id, start, end)
    
    # retrieve the leaderboard for a single game WITHOUT score
    def get_leaderboard_no_score(self, game_id: int, start : int, end : int):
        return self.leaderboard_redis.retrieve_leaders_no_score(game_id, start, end)
    
    # retrieve user's rank for all games
    def get_rankings_all_games(self, user_id : int):
        return self.leaderboard_redis.user_data_all_games(user_id)
    
    # retrieve leaders and create top player report
    def retrieve_top_player_report(self, game_id : int):
        # get the current top 10 from redis
        leaders = self.get_leaderboard_no_score(game_id, 0 , 9)
        # get info on the top 10 from postgres
        leaders_report = self.get_player_info(leaders)
        return leaders_report
    
    def get_game_cache_or_add_db(self, game_id ):
        # read game name from cache
        game_name = self.get_game_cache(game_id)

        # if not in cache, retrieve from db and add to cache
        if game_name is None:
            db_game = self.get_game_pg(game_id)
            if db_game:
                game_name = db_game.name
                self.add_game_cache(game_name, game_id)   
            else:
                return None
        return game_name 

        