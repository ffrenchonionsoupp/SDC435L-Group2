# SDC435L-Group2
This is a repository for SDC435L Group 2's GitHub Archive Explorer application.

# GitHub Archive Explorer
A menu-driven Python command-line application that loads the course **GitHubArchive-Dataset** (GitHub repository data: commits, programming languages, licenses, and watcher counts) and stores, queries, and analyzes it using a different database each week:

| Week | Database  | Type                  | Status       |
|------|-----------|-----------------------|--------------|
| 1    | Redis     | In-memory key-value   | Complete     |
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
### 3. Start Redis
#### Linux
```bash
sudo apt install redis-server
sudo service redis-server start
redis-cli ping
# Expected output: PONG
```
### 4. Add the dataset
The dataset is **not** included in the repository because it is too large for GitHub.

1. Download `GitHubArchive-Dataset.zip` from the course page or https://ecpi.instructure.com/courses/168279/files/42293011?verifier=j69DUlactxQ5XhqHNnAgvTdNuGMOSme9cpDj3ODC&wrap=1
2. Create a `data` folder in the project root and put the zip inside it, **without unzipping it**:
   ```
   SDC435L-Group2/data/GitHubArchive-Dataset.zip
   ```

The application reads the files straight from the zip.

### 5. Configure environment variables (optional)
Only needed if your Redis settings or dataset location are different. Create a file named `.env` in the project root:
```env
REDIS_HOST=localhost
REDIS_PORT=6379
DATA_PATH=data/GitHubArchive-Dataset.zip
```
`DATA_PATH` can also point to the zip somewhere else (for example `~/Downloads/GitHubArchive-Dataset.zip`), or to a folder of the extracted `.json` files.

| File | Records | Contents | Used in Week 1 |
|---|---|---|---|
| `Commits.json`, `Sample_Commits.json` | 25,000 each | Commit hash, author, committer, message, parent commits, repository name | CRUD, Feature 3 |
| `Languages.json` | ~3.3 million | Each repository's languages and bytes of code | Feature 1 |
| `Sample_Repos.json` | 400,000 | Repository name and watch count | Feature 2 |
| `Licenses.json` | 25,000 | Repository name and license | Feature 2 |
| `Files.json`, `Contents.json` (+ samples) | 25,000 each | File paths and file contents | Later weeks |

---

## Running the Application
From the project root:
```bash
python3 main.py
```
### Main menu
```
 ★ ★ ★ GitHub Archive Explorer  ★ ★ ★
1. Redis
2. MongoDB    (coming Week 2)
3. Cassandra  (coming Week 3)
4. Neo4j      (coming Week 4)
5. SQLite     (coming Week 5)
0. Exit
```
### Redis menu
```
 ★ Redis(0 commits stored)★
1. Load dataset into Redis
2. Create a commit
3. Read a commit
4. Update a commit
5. Delete a commit
6. Language leaderboard
7. Repository popularity & licenses
8. Commit search & top contributors
0. Back to main menu
```
**Run option 1 first** to load the dataset before using options 2–8. Loading takes a minute or two because `Languages.json` is large.

### Things to try
- **Options 3–5:** copy one of the sample commit hashes that are shown.
- **Option 7 → 2:** look up `FreeCodeCamp/FreeCodeCamp` or `apple/swift`.
- **Option 8 → 1:** search commit messages for `memory leak`.

---

## Week 1 Features (Redis)

| Feature | Description | Redis structures | Dataset files |
|---|---|---|---|
| **Data loader** | Reads each file line by line and sends data to Redis in batches with pipelines. Skips commits that appear in both commit files. Asks before clearing and reloading. | Pipelines | Commits, Sample_Commits, Sample_Repos, Licenses, Languages |
| **CRUD** | Create, read, update, and delete commits by commit hash. New commits get a Git-style SHA-1 hash. Updates and deletes also update the rankings and search index. | Strings `commit:<hash>`, Set `commits` | Commits, Sample_Commits |
| **1. Language leaderboard** | Ranks languages by number of repositories or by total bytes of code. | Sorted Sets `lang_repos`, `lang_bytes` (`ZREVRANGE`) | Languages |
| **2. Repository popularity & licenses** | Most-watched repositories, license breakdown, and a lookup showing one repository's watchers, rank, license, languages, and commit count. | Sorted Sets `repo_watchers`, `license_counts` (`ZSCORE`, `ZREVRANK`); Hashes `repo_licenses`, `repo_languages` | Sample_Repos, Licenses, Languages |
| **3. Commit search & top contributors** | Keyword search on commit messages (finds commits containing every keyword), most active authors, and repositories with the most commits. | Sets `word:<word>` (`SINTER`); Sorted Sets `top_authors`, `repo_commits` | Commits, Sample_Commits |

---

## Project Structure
```
.
├── main.py           # Application: menus, Redis CRUD, and analysis features
├── data/             # GitHubArchive-Dataset.zip goes here (not committed)
├── requirements.txt
├── .env              # Optional local settings (not committed)
└── README.md
```

---

## Troubleshooting
| Problem | Fix |
|---|---|
| `ERROR: Could not connect to Redis` | Start Redis (`sudo service redis-server start`) and check with `redis-cli ping`. |
| `ModuleNotFoundError: No module named 'redis'` | Run `pip install -r requirements.txt`. |
| `Commits.json not found - skipped` | Make sure the zip is at `data/GitHubArchive-Dataset.zip`, or set `DATA_PATH` to where it is saved. |
| Keyword search finds nothing | Use words with 3+ letters. Very common words (e.g. "the", "fix", "update") are not indexed. |
| Want a fresh start | Choose option 1 and answer `y` to clear and reload. |
