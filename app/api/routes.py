from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from datetime import datetime, timedelta, timezone
import logging
from .database import SessionDep
from .auth import get_current_user, login_for_access_token, authenticate_user, create_access_token
from .schema import Token, UserInput, UserPublic, ScorePublic, ScoreInput, SingleRankWithScore, GameLookUp, GameID, GameIDInput, MultipleRanks, TopPlayerList
from .models import User, Score, Game
from data.data_service import DataService, DataServiceException
from sqlalchemy.exc import IntegrityError, OperationalError
from redis.exceptions import ConnectionError, RedisError


ACCESS_TOKEN_EXPIRE_MINUTES = 30

### 0 SETUP ###

## router ## 

router = APIRouter()


## logger ##

# initialize logger 
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s",
                    handlers=[
        logging.StreamHandler(),  # Logs to console
        logging.FileHandler("app.log")  # Logs to file
    ])

logger = logging.getLogger(__name__)


## error handling ##

def log_and_raise_error(message: str, status_code: int = 500):
    logger.error(message)
    raise HTTPException(status_code=status_code, detail=message)


## check if current user is the owner of the resource requested

def check_user(current_user : int , user_id : int):

    if current_user != user_id:
        raise HTTPException(status_code=401, detail=f'you do not have permission to view this resource for user {current_user}')

## --------------------##
### 1. ENDPOINTS ###
## --------------------##


## 1.1 register ##
 
# /users 
# POST
# register endpoint
@router.post("/users/register/", response_model=UserPublic)
def create_user(user: UserInput, session: SessionDep):
    # add the user to the database.
    try:
        data_service = DataService(session, logger)
        new_user = data_service.add_user(user)
    except DataServiceException as e:
        log_and_raise_error(f"DataServiceError: {e}", 500)
    except Exception as e:
        log_and_raise_error(f"Error trying to create user: {e}", 500)

    # add the username to the cache
    try:
        data_service.set_user_cache(new_user.username, new_user.id)
    except DataServiceException as e:
        # no exception raised if user is not added to the cache
        logger.error(f"DataServiceError: {e}")
    return new_user


## 1.2 login ##

# /login
# POST 
# register endpoint
@router.post("/auth/token")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep
) -> Token:
    
    # verify user details
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        log_and_raise_error(f"Incorrect username or password", 401)
    
    # create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    try:
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
    except Exception as e:
        log_and_raise_error(f"Failed to create access token : {e}", 500)

    # return token
    return Token(access_token=access_token, token_type="bearer")


## 1.3 list of games ##

#games/list
# GET
# ids for games
# postgres
@router.get("/games", response_model=GameLookUp)
def all_game_ids(session : SessionDep,
                  current_user: Annotated[User, Depends(get_current_user)]):
    
    # retrieve game list from db
    try:
        data_service = DataService(session, logger)
        data = data_service.get_list_games()

    except DataServiceException as e:
        log_and_raise_error(f"Error reading from db: {e}", 404)
    
    # format game list
    all_games_string_keys = {str(k): v for k,v in data.items()}
    formatted_data = GameLookUp(games = all_games_string_keys)

    return formatted_data
 

## 1.4 create a new game entry ##

# /games
# POST
# admin route to add new games
# postgres
# TODO limit to admin staff. 

@router.post("/games", response_model=GameID)
def add_game(game: GameIDInput, 
             session : SessionDep,
             current_user: Annotated[User, Depends(get_current_user)]):
    
    if current_user.is_admin != True:
        log_and_raise_error(f'You do not have permission to view this resource', 401)
    
    data_service = DataService(session, logger)
    new_game = data_service.add_game(game)

    return new_game


## 1.5 submit a score ##

# /users/{user_id}/scores
# POST
# score submission 
# redis & pg
@router.post("/users/{user_id}/scores", response_model=ScorePublic)
def submit_scores(user_id : int, 
                  score: ScoreInput, 
                  session: SessionDep, 
                  current_user: Annotated[User, Depends(get_current_user)]):
    
    # ensure current user matches user_id
    check_user(current_user.id, user_id)

    data_service = DataService(session, logger)
    new_score = data_service.submit_score(score, user_id) 
    
    return new_score



## 1.6 leaderboard for one game ##

# games/leaderboard/{game_id}
# GET
# leaderboard for a single game
# redis

@router.get("/games/leaderboard/{game_id}")
def leaderboard_single_game(game_id: int,
                            session : SessionDep,
                            current_user: Annotated[User, Depends(get_current_user)],
                            start: int = Query(0, ge=0),
                            end: int = Query(9, ge=4)):

    # fetch the leaders
    data_service = DataService(session, logger)
    data = data_service.get_leaderboard_with_score(game_id, start, end)

    # if no data, return early
    if not data:
        log_and_raise_error("No leaderboard data found", 404)
    
    # selects the user ids of the leaders
    user_ids = [entry[0] for entry in data]

    # gets data for multiple users from redis
    usernames = data_service.get_mutiple_usernames(user_ids)
    
    # query missing usernames, add them to the data and then add to cache
    if None in usernames:
        #pick out the user_ids where we don't have the username
        missing_usernames = [user_id for user_id, username in zip(user_ids, usernames) if username is None]
        # fetch the data from postgres. 
        missing_data = data_service.get_multiple_users(missing_usernames)

        # put data into a dict for referencing below
        missing_data_dict= {row.id : row.username for row in missing_data}

        # zip together user_ids and usernames, if username is none then look for missing username in missing_data_dict
        usernames = [
        missing_data_dict.get(user_id, user_id) if username is None else username
        for user_id, username in zip(user_ids, usernames)
    ]

    # lookup game name using game id
    game_name = data_service.get_game_cache_or_add_db(game_id)
    if game_name is None:
        logger.error('failed to retrieve game : {game_id}')
        raise HTTPException(detail="Failed to retrieve game name", status_code=404)


    if len(data) != len(usernames):
        raise HTTPException(detail="Error in formatting data", status_code=500)

    response_data = [
        {
            "rank": start + idx + 1,
            "username": username,
            "score": entry[1]
        }
        for idx, (entry, username) in enumerate(zip(data, usernames))
]
   
    return {"game" :game_name, "data": response_data}


## 1.7 user's ranking for a game ##

# users/{user_id}/ranking/{game_id}
# GET
# user's rankings for a single game
# redis
@router.get("/users/{user_id}/ranking/{game_id}")
def user_score_single_game(user_id: int, game_id,
                           current_user: Annotated[User, Depends(get_current_user)],
                           session : SessionDep) -> SingleRankWithScore:
    
    # ensure current user is asking about their own resource
    check_user(current_user.id, user_id )
    
    # retrieve rank and score from redis
    data_service = DataService(session, logger)

    try:
        rank, score = data_service.get_single_ranking(user_id, game_id)
        if rank is None or score is None:
            logger.error(f'Failed to find score or rank for user {user_id} and game {game_id}')
            raise HTTPException(status_code=400, detail="Could not find the rank of the user for this game.")
    except ConnectionError:
        raise HTTPException(status_code=503, detail="Redis connection failed.")
    except Exception as e:
        log_and_raise_error(f"Unexpected error occurred: {e}", 500)
    
    # get game name
    game_name = data_service.get_game_cache_or_add_db(game_id)

    return {"game" : game_name, "rank": rank, "score" : score}


## 1.8 lists the user's ranks for all games ##

# users/{user_id}/ranking
# GET
# user's rankings for all games
@router.get('/users/{user_id}/ranking')
def users_rankings_all_game(user_id : int, 
                            current_user: Annotated[User, Depends(get_current_user)],
                            session : SessionDep):
    
    # ensure current user is asking about their own resource
    check_user(current_user.id, user_id)

    # retrieve data from redis
    data_service = DataService(session, logger)
    results = data_service.get_rankings_all_games(user_id)

    all_games = data_service.get_list_games()

    all_games_string_keys = {str(k): v for k,v in all_games.items()}

    results_with_names = {all_games_string_keys[k] : v for k,v in results.items()}


    # raise exception or return the data
    if results == None:
        raise HTTPException(status_code=404, detail = "No ranking information found")
    
    return results_with_names


## 1.9 info on the top 10 players for an individual game

# games/{game_id}/leaders
# GET
# top players report for a single game
@router.get('/games/{game_id}/leaders')
def top_players(game_id : int,
                current_user: Annotated[User, Depends(get_current_user)],
                session : SessionDep):

    # retrieve info on the top 10 players
    data_service = DataService(session, logger)

    leaders_data = data_service.retrieve_top_player_report(game_id)

    if leaders_data is None:
        return HTTPException(status_code=404, detail = 'Failed to find top player report data')
    
    return leaders_data

