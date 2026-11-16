# SDC435L-Group2
This is a repository for SDC435L Group 2's GitHub Archive Explorer application.

# GitHub Archive Explorer
A menu-driven Python command-line application that loads public GitHub activity events from the [GitHub Archive](https://www.gharchive.org/) dataset and stores, queries, and analyzes them using a different database each week:

| Week | Database  | Type                  | Status       |
|------|-----------|-----------------------|--------------|
| 1    | Redis     | In-memory key-value   | Complete  |
| 2    | MongoDB   | Document              | Planned...   |
| 3    | Cassandra | Wide-column           | Planned...   |
| 4    | Neo4j     | Graph                 | Planned...   |
| 5    | SQLite    | Relational            | Planned...   |

## Team Members
- Francis Hampton
- Emily Gillespie
- Daniel Dobyns
- Joshua Taylor


## Prerequisites
- **Python 3.10+** 
- **Git**
- **Redis Server 7.x** 

## Setup
### 1. Clone the repository
```bash
git clone https://github.com/ffrenchonionsoupp/SDC435L-Group2.git
cd SDC435L-Group2
```
### 2. Install dependencies
```bash
pip install -r requirements.txt
```
### 4. Start Redis
#### Linux
```bash
sudo apt install redis-server
sudo service redis-server start
redis-cli 
ping
# Expected output: PONG
```
### 5. Configure environment variables
Create a file named `.env` in the project root:
```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
DATA_PATH=data/
```
### 6. Dataset

The GitHub Archive dataset is included in the repository in the `data/` folder, so no separate download is needed. It is cloned automatically with the project.

The application reads newline-delimited JSON files (`.json`) and gzipped files (`.json.gz`) from the folder set by `DATA_PATH` in `.env` (default: `data/`).

---

## Running the Application
From the project root:
```bash
python main.py
```
### Main menu
```
★★★ GitHub Archive Explorer ★★★
1. Redis
2. MongoDB    (coming Week 2)
3. Cassandra  (coming Week 3)
4. Neo4j      (coming Week 4)
5. SQLite     (coming Week 5)
0. Exit
```
### Redis menu
```
  ★ Redis ★
1. Load dataset into Redis
2. Create an event
3. Read an event by ID
4. Update an event
5. Delete an event
6. Event type leaderboard
7. Most active users / repositories
8. Time-window activity search
0. Back to main menu
```
**Run option 1 first** to load the dataset before using options 2–8.

---

## Week 1 Features (Redis)

All features use the event JSON from the GitHub Archive dataset. Each event contains an `id`, `type`, `actor`, `repo`, `payload`, and `created_at` timestamp.

| Feature | Description | Redis structures | Dataset fields |
|---|---|---|---|
| **Data loader** | Streams the dataset line by line and stores each event as JSON under `event:<id>`, using a pipeline for fast bulk writes. Builds the feature indexes while loading. | Strings, Pipeline | All |
| **CRUD** | Create, read (pretty-printed), update, and delete individual events. Deleting an event also removes it from the indexes. | Strings, Sorted Sets | All |
| **Event type leaderboard** | Ranks all event types (PushEvent, WatchEvent, etc.) by frequency. | Sorted Set `event_types` (`ZINCRBY`, `ZREVRANGE`) | `type` |
| **Most active users / repos** | Shows the top N users or repositories by number of events. | Sorted Sets `top_actors`, `top_repos` | `actor.login`, `repo.name` |
| **Time-window search** | Returns events between a start and end time, plus an hour-by-hour activity summary. | Sorted Set `events_by_time` (`ZRANGEBYSCORE`), Hash `hourly_counts` | `created_at` |

---

## Project Structure
```
.
├── main.py                 # Entry point and main menu
├── data/                   # GitHub Archive dataset (included)
├── data_loader.py          # Shared JSON / .json.gz reader for all databases
├── redis_module/
│   ├── __init__.py
│   ├── connection.py       # Redis client setup from .env
│   ├── crud.py             # Create, Read, Update,
