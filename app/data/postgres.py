from fastapi import HTTPException
from api.database import SessionDep
import logging
from typing import List 
from sqlmodel import select
from sqlalchemy.exc import IntegrityError
from redis.exceptions import RedisError
from api.models import User, Game, Score
from api.schema import UserInput, GameID, GameLookUp, GameIDInput
from api.database import SessionDep
from api.auth import get_password_hash

class DBError(Exception):
    """Custom exception for sql database."""
    pass 

class PostgresClient:
    
    def __init__(self, session : SessionDep, logger):
        self.session = session
        self.logger = logger
     

    #       HELPER FUNCTIONS  
    # ------------------------------------------------#

    ### 0.1 ERROR LOGGING AND EXCEPTION RAISING ###
    def log_and_raise_error(self, message: str):
        self.logger.error(message)
        raise DBError(message)


    ### 0.2 RETREIVE FULL USER INFO FROM POSTGRES ###
    def retrieve_multiple_usernames_pg(self, list_of_ids : List[str]):
        # get data from postgres
        try:
            data = self.session.exec(select(User).where(User.id.in_(list_of_ids))).all()
        except Exception as e:
            self.logger.error(f"Failure to read data from db: {e} for users: {list_of_ids}")
            return None
        
        if data is None:
            self.logger.error('Failed to retrieve data from db')
            return None
            
        return data

    # ------------------------------------------------#
    #       USER FUNCTIONS  
    # ------------------------------------------------#

    ### 1.0 CREATE A NEW USER ###

    def add_user(self, user: UserInput):
        #get hashed password
        try:
            hashed_password = get_password_hash(user.plain_password)
        except Exception as e:
            self.log_and_raise_error(f"Error hashing password: {e}")
        
        #create new User instance
        try: 
            new_user = User(email = user.email, username=user.username, country=user.country, hashed_password=hashed_password, is_admin=user.is_admin)
            self.session.add(new_user)
            self.session.commit()
            self.session.refresh(new_user)
            
        except IntegrityError as e:
            self.session.rollback()
            self.log_and_raise_error(f"User with this username/email already exists: {e}")
        except Exception as e:
            self.log_and_raise_error(f"Error adding user to db: {e}")

        # return user
        return new_user 


    ### 2.0 GET TOP PLAYER INFORMATION ###

    # take list of leaders [ids] and return dict with {rank : {username: (username), country: (country), date joined : (date)} 
    def get_player_info(self, leaders : List[str]):
        
        # get the postgres data
        leaders_data = self.retrieve_multiple_usernames_pg(leaders)

        # return if no data
        if leaders_data == None:
            return None
        
        # prepare leaders_data
        data_to_include= {'username', 'country', 'date_added'}

        cleaned_leaders_data = {str(leader.id) : {key: getattr(leader, key) for key in data_to_include} for leader in leaders_data}

        # add ranks and map data to the correct position as in the ordered redis list
        ordered_leaders_data =  [
        {"rank": f"{i + 1}", **cleaned_leaders_data[str(user_id)]}
        for i, user_id in enumerate(leaders)
        ]

        return ordered_leaders_data


    # get the full list of games
    def get_games(self):
        try:
            games = self.session.exec(select(Game)).all()
            game_dict = {game.id : game.name for game in games}
            return game_dict
            # return GameLookUp(games = [GameID(id = game.id, name=game.name) for game in games])
        except Exception as e:
            self.log_and_raise_error(f"Error when retrieving data: {e}", 500)


    # add game to db
    def add_game_pg(self, game: GameIDInput):
        try:
            new_game = Game(name = game.name)
            self.session.add(new_game)
            self.session.commit()
            self.session.refresh(new_game)
            
        except IntegrityError as e:
            self.session.rollback()
            self.log_and_raise_error(f"Game with this name already exists: {e}", 400)
        except Exception as e:
            self.log_and_raise_error(f"Error adding user to db: {e}", 500)
        
        return new_game
        

    # retrieve a game using it's id
    def get_game_pg(self, game_id):
        try:
            self.session.get(game_id)
        except Exception as e:
            self.log_and_raise_error(f"error reading game name : {e}", 500)


    # add a single game
    def submit_score(self, user_id : int, score):
        try:
            # add to postgres
            new_score = Score(user_id = user_id, game_id=score.game_id, score=score.score)
            self.session.add(new_score)
            self.session.commit()
            self.session.refresh(new_score)
        except Exception as e:
            self.log_and_raise_error(f"Error adding score to db: {e}", 500)
          
        return new_score
