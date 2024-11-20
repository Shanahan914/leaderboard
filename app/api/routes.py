from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from datetime import timedelta
import logging
from .database import SessionDep
from .auth import authenticate_user, create_access_token, get_password_hash, get_current_user
from .schema import Token, UserInput, UserPublic, ScorePublic, ScoreInput, SingleRankPublic, GameLookUp, GameID, GameIDInput
from .models import User, Score, Game
from leaderboard_service.leaderboard import retry_submit_score, retrieve_ranking, retrieve_leaders, retry_set_user_cache, retry_set_game_cache, get_game_cache, get_user_cache, get_multiple_usernames
from sqlmodel import select
from sqlalchemy.exc import IntegrityError, OperationalError
from redis.exceptions import ConnectionError, RedisError
import copy


ACCESS_TOKEN_EXPIRE_MINUTES = 30

### 0 SETUP ###


## 0.1 router ## 

router = APIRouter()


## 0.2 logger ##

# initialize logger 
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s",
                    handlers=[
        logging.StreamHandler(),  # Logs to console
        logging.FileHandler("app.log")  # Logs to file
    ])

logger = logging.getLogger(__name__)


## 0.3 error handling ##
def log_and_raise_error(message: str, status_code: int = 500):
    logger.error(message)
    raise HTTPException(status_code=status_code, detail=message)


## 0.4 read from postgres

def read_db_value(operation, session, id, model, attribute: str):
    try:
        value = operation(id)
        if not value:
            raise ValueError('Cache miss')
        
    except ValueError as e:
        logger.error(f'cache miss for {model.__name__}: {id}')
        data = session.get(model, id)
        value = getattr(data, attribute, None) if data else None

    except Exception as e:
        logger.error(f'Failed to read {model.__name__} from redis: {e}')
        data = session.get(model, id)
        value = getattr(data, attribute, None) if data else None

    if not value:
        log_and_raise_error(f"Failed to read game from cache or db for game_id {id}")
    return value 


## --------------------##
### 1. ENDPOINTS ###
## --------------------##


## 1.1 register ##
 
# /users 
# POST
# register endpoint
@router.post("/users/register/", response_model=UserPublic)
def create_user(user: UserInput, session: SessionDep):
    #get hashed password
    try:
        hashed_password = get_password_hash(user.plain_password)
    except Exception as e:
        log_and_raise_error(f"Error hashing password: {e}", 400)
    
    #create new User instance
    try: 
        new_user = User(email = user.email, username=user.username, hashed_password=hashed_password, is_admin=user.is_admin)
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        
    except IntegrityError as e:
        session.rollback()
        log_and_raise_error(f"User with this username/email already exists: {e}", 400)
    except RedisError as e:
        log_and_raise_error(f"Error adding to cache : {e}", 400)
    except Exception as e:
        log_and_raise_error(f"Error adding user to db: {e}", 400)
    
    # set id _> username in cache
    retry_set_user_cache(new_user.username, new_user.id)

    return new_user


## 1.2 login ##

# /login
# POST 
# register endpoint
@router.post("/auth/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep
) -> Token:
    print( form_data.username)
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


## 1.3 list of games ##

#games/list
# GET
# ids for games
# postgres
@router.get("/games", response_model=GameLookUp)
def all_game_ids(session : SessionDep):
    try:
        games = session.exec(select(Game)).all()
        return GameLookUp(games = [GameID(id = game.id, name=game.name) for game in games])
    except Exception as e:
        log_and_raise_error(f"Error when retrieving data: {e}", 500)


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
        raise HTTPException(status_code=401, detail=f'You do not have permission to view this resource.')
    try:
        new_game = Game(name = game.name)
        session.add(new_game)
        session.commit()
        session.refresh(new_game)
        
    except IntegrityError as e:
        session.rollback()
        log_and_raise_error(f"Game with this name already exists: {e}", 400)
    except Exception as e:
        log_and_raise_error(f"Error adding user to db: {e}", 500)
    
    # add id -> name to cache
    retry_set_game_cache(new_game.name, new_game.id)

    return new_game


## 1.5 submit a score ##

# /users/{user_id}/scores
# POST
# score submission 
# redis & pg
@router.post("/users/{user_id}/scores", response_model=ScorePublic)
def submit_scores(user_id : int, score: ScoreInput, session: SessionDep):
    try:
        # add to postgres
        new_score = Score(user_id = user_id, game_id=score.game_id, score=score.score)
        session.add(new_score)
        session.commit()
        session.refresh(new_score)
    except Exception as e:
        log_and_raise_error(f"Error adding score to db: {e}", 500)
     # add to redis
    retry_submit_score(score, user_id)
    
    return new_score



## 1.6 leaderboard for one game ##

# games/leaderboard/{game_id}
# GET
# leaderboard for a single game
# redis
### TODO currently returning user_id add score. Problaby need to add a username for this actually and then return that. 
##
@router.get("/games/leaderboard/{game_id}")
def leaderboard_single_game(game_id: int,
                            session : SessionDep,
                        start: int = Query(0, ge=0),
                        end: int = Query(9, ge=4)):
    # retrieve from redis
    try:
        data = retrieve_leaders(game_id, start, end)
    except RedisError as e:
        log_and_raise_error(f'Failed to fetch leaders for game {game_id} : {e}', 500)

    # if no data, return early
    if not data:
        HTTPException(status_code=404, detail="No leaderboard data found")
    
    # lookup usernames for the leaders
    user_ids = [entry[0] for entry in data]
    usernames = get_multiple_usernames(user_ids)
    formatted_usernames = [ name if name != None else "Anonymous user" for name in usernames ]

    # lookup game name using game id
    game_name = read_db_value(get_game_cache, session, game_id, Game, 'name')

    # construct response
    response_data = []
    rank = start

    if len(data) != len(formatted_usernames):
        HTTPException(detail="Error in formatting data", status_code=500)

    for i in range(len(data)):
        rank += 1
        response_data.append({
            "rank": rank, 
            "username": formatted_usernames[i], 
            "score": data[i][1]})
   
    return {"game" :game_name, "data": response_data}


## 1.7 user's ranking for a game ##

# users/{user_id}/ranking/{game_id}
# GET
# user's rankings for a single game
# redis
@router.get("/users/{user_id}/ranking/{game_id}")
def user_score_single_game(user_id: int, game_id,
                           current_user: Annotated[User, Depends(get_current_user)],
                           session : SessionDep) -> SingleRankPublic:
    # ensure current user is asking about their own resource
    if current_user.id != user_id:
        raise HTTPException(status_code=401, detail=f'you do not have permission to view this resource. {current_user.id}')
    
    # retrieve rank and score from redis
    try:
        rank, score = retrieve_ranking(user_id, game_id)
        if rank is None or score is None:
            raise HTTPException(status_code=400, detail="Could not find the rank of the user for this game.")
    except ConnectionError:
        raise HTTPException(status_code=503, detail="Redis connection failed.")
    except Exception as e:
        log_and_raise_error(f"Unexpected error occurred: {e}", 500)
    if rank == None or score == None:
        raise HTTPException(status_code=400, detail=f'Could not find the rank of the user for this game. Please check the provided details.')
    
    # get game name
    game_name = read_db_value(get_game_cache, session, game_id, Game, 'name')

    return {"game" : game_name, "rank": rank, "score" : score}




#### NOT STARTED 

# users/{user_id}/ranking
# GET
# user's rankings for all games
# redis



# games/{game_id}/leaders
# GET
# top players report for a single game
# pg


# games/leaderboard
# GET
# leaderboard for all games
# redis