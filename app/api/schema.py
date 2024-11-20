from pydantic import BaseModel 
from enum import Enum
from datetime import datetime
from typing import List 

### 1. USER ###

# user input
class UserInput(BaseModel):
    username : str
    email: str 
    plain_password: str
    is_admin: bool | None = None

# user for public
class UserPublic(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool | None = None

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

class SingleRankPublic(BaseModel):
    game: str
    rank : int
    score : float 


### 5. Game ids 

class GameIDInput(BaseModel):
    name : str

class GameID(GameIDInput):
    id: int

class GameLookUp(BaseModel):
    games: List[GameID]