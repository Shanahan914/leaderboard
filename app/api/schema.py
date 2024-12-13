from pydantic import BaseModel 
from enum import Enum
from datetime import datetime
from typing import List 
from datetime import datetime

### 1. USER ###

# user input
class UserInput(BaseModel):
    username : str
    email: str 
    country : str
    plain_password: str
    is_admin: bool | None = None

# user for public
class UserPublic(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool | None = None
    country : str

# user for internall (full)
class UserPrivate(UserPublic):
    hashed_password: str
    is_admin: bool | None = None

    class Config:
        from_attributes = True  # Enables from_orm() to work with SQLModel model
    

### 2. JWT Token ###

# jwt token
class Token(BaseModel):
    access_token: str
    token_type: str


# data encoded in JWT
class TokenData(BaseModel):
    email: str | None = None


### 3. Score ###

class ScoreInput(BaseModel):
    score : float
    game_id : int

class ScorePublic(BaseModel):
    id : int
    user_id : int
    score : float
    game_id : int
    date_added : datetime

### 4. Rank ###

class SingleRank(BaseModel):
    game: str
    rank : int

class SingleRankWithScore(SingleRank):
    score : float 

class MultipleRanks(BaseModel):
    games : List[SingleRank]


### 5. Game ids 

class GameIDInput(BaseModel):
    name : str

class GameID(GameIDInput):
    id: int

class GameLookUp(BaseModel):
    games: List[GameID]


### 6. Player profile

class TopPlayerInfo(BaseModel):
    username : str
    country : str
    date_joined : datetime


class TopPlayerList(BaseModel):
    leaders : List[TopPlayerInfo]