# Real-Time Leaderboard System

## Overview
This project implements a real-time leaderboard system where users can register, log in, and submit scores for various games or activities. The system uses **Redis sorted sets** for efficient storage, real-time updates, and querying of leaderboard data. Redis is also used as a cache for quick transformations between ids and names. Users can view global leaderboards, their rankings, and generate reports on top players. 

This is a solution to the roadmap.sh project leadboard: https://roadmap.sh/projects/realtime-leaderboard-system

---

## Features

### 1. **User Authentication**
- Users can **register** and **log in** to the system.
- Authentication is handled securely using hashed passwords and JWT. 

### 2. **Score Submission**
- Users can submit their scores for different games or activities.
- Each game has its own leaderboard stored as a Redis sorted set.

### 3. **Leaderboard Updates**
- The global leaderboard displays the top users across all games.
- Real-time updates are enabled using Redis sorted sets.

### 4. **User Rankings**
- Users can view their rankings on the leaderboard for specific games or globally.
- Rank queries are handled using Redis commands like `ZREVRANK` and `ZSCORE`.

### 5. **Top Players Report**
- Generate reports on the top players for specific periods (e.g., daily, weekly, monthly).
- Periodic leaderboards are stored as separate Redis sorted sets with expiration times.

---

## Technologies Used

- **Backend**: Python (FastAPI)
- **Database**: PostgreSQL (for user data), Redis (for leaderboards)
- **Authentication**: JWT (JSON Web Tokens)
- **Real-Time Updates**: Redis Sorted Sets
- **Containerization**: Docker

---

## Setup and Installation

### Prerequisites
- Python 3.8+
- Docker and Docker Compose
- Redis and PostgreSQL (or use Docker containers)

### Steps
1. **Clone the Repository**:
   ```bash
   git clone <repo-url>
   cd real-time-leaderboard
   pip install -r requirements.txt
   ```
2. Set up a .env file with the following:
   ```
   DATABASE_URL=postgresql://user:password@localhost/dbname
   REDIS_URI=redis://localhost:6379
   SECRET_KEY=your_secret_key
   ```
3. Run with docker:
   ```
   docker-compose up --build
   ```

## API Endpoints

### Authentication
- `POST /register`: Register a new user.
- `POST /login`: Log in and get a JWT token.

### Leaderboard
- `POST users/{user_id}/scores`: Submit a score for a game.
- `POST /games`: Create a new game
- ` GET /users/{user_id}/{game_id}` : Get the user's rank for a specific game.
- ` GET /users/{user_id}` : Get the user's rank for all games.
-  `GET /games`: Get a list of games on the leaderboard
- `GET games/leaderboard/{game_id}`: Get the leaderboard for a specific game.
- `GET /rank/{user_id}`: Get the rank of a specific user.

### Reports
- `GET games/{games_id}/leaders`: Generate a report for the top players in a specific game
