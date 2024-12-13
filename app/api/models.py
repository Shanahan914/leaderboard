from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from typing import List
from datetime import datetime
from enum import Enum


class User(SQLModel, table=True):
    id : Optional[int] = Field(default=None, primary_key=True)
    username : str = Field(unique=True, nullable=False)
    email : str = Field(unique=True, nullable=False)
    hashed_password : str = Field(nullable=False)
    country : str = Field(nullable=False)
    is_active : bool = Field(default=True)
    is_admin : bool = Field(default=False)
    date_added : datetime = Field(default_factory=datetime.utcnow, nullable=False)
    score_user : List["Score"] = Relationship(back_populates="user")


class Game(SQLModel, table=True):
    id : Optional[int] = Field(default=None, primary_key=True)
    name : str = Field(nullable=False, unique=True)
    game_scores : List["Score"] = Relationship(back_populates="game")
    date_added : datetime = Field(default_factory=datetime.utcnow, nullable=False)


class Score(SQLModel, table=True):
    id : Optional[int] = Field(default=None, primary_key=True)
    user_id : Optional[int] = Field(default=None, foreign_key="user.id")
    user : Optional["User"] = Relationship(back_populates="score_user")
    score : float = Field(nullable=False)
    game_id : Optional[int] = Field(default=None, foreign_key="game.id")
    game : Optional["Game"] = Relationship(back_populates="game_scores")
    date_added : datetime = Field(default_factory=datetime.utcnow, nullable=False)


