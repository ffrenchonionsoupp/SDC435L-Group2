"""
 Names:       Francis Hampton, Emily Gillespie, Daniel Dobyns, and Joshua Taylor
 Date:        November 15, 2026
 Assignment:  SDC435L Group Project - Week 1: Redis Integration
 Program:     GitHub Archive Explorer (main.py)
 Objective:   A menu-driven Python application that imports the
              GitHubArchive-Dataset into a Redis key-value database,
              performs CRUD (Create, Read, Update, Delete) operations on
              commit records, and provides three analysis features:
                1. Language leaderboard                (Sorted Sets)
                2. Repository popularity & licenses    (Sorted Sets + Hashes)
                3. Commit keyword search & top authors (Sets + Sorted Sets)
"""

import hashlib
import json
import os
import time
import zipfile

import redis

# Read settings from a .env file if python-dotenv is installed (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --
# Settings
# --
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
DATA_PATH = os.path.expanduser(os.getenv("DATA_PATH", "data/"))  # the .zip or a folder

# Common words that are not added to the keyword search index
STOP_WORDS = {"the", "and", "for", "with", "from", "this", "that", "into",
              "add", "fix", "update", "remove", "use", "new", "not", "are"}


# --
# Helper functions
# --
def connect():
    """Connect to Redis and make sure the server is running."""
    print("Connecting to Redis at {}:{}...".format(REDIS_HOST, REDIS_PORT))
    r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    try:
        r.ping()
    except redis.exceptions.ConnectionError:
        print("\nERROR: Could not connect to Redis.")
        print("Start the redis server and check it with: redis-cli ping")
        return None
    print("Connected!!")
    return r


def read_file(name):
    """Yield each JSON record in a dataset file (from the .zip or a folder)."""
    if DATA_PATH.lower().endswith(".zip"):
        z = zipfile.ZipFile(DATA_PATH)
        member = next((m for m in z.namelist() if os.path.basename(m) == name), None)
        if member is None:
            print("  {} not found - skipped".format(name))
            return
        f = (line.decode("utf-8") for line in z.open(member))
    else:
        found = [os.path.join(root, name) for root, _, files in os.walk(DATA_PATH) if name in files]
        if not found:
            print("  {} not found - skipped".format(name))
            return
        f = open(found[0], encoding="utf-8")

    print("  Loading {}".format(name))
    for line in f:
        if line.strip():
            yield json.loads(line)


def repo_of(commit):
    """repo_name is a list in Commits.json but plain text in Sample_Commits.json."""
    repo = commit.get("repo_name") or "unknown"
    return repo[0] if isinstance(repo, list) else repo


def author_of(commit):
    return (commit.get("author") or {}).get("name") or "unknown"


def words_in(commit):
    """Unique, lowercase words (3+ letters) from a commit message."""
    words = set()
    for word in (commit.get("message") or "").lower().split():
        word = word.strip(".,:;!?()[]{}'\"`#*")
        if len(word) >= 3 and word.isalpha() and word not in STOP_WORDS:
            words.add(word)
    return words


def index_commit(pipe, commit, amount):
    """Add (amount=1) or remove (amount=-1) a commit from the search/ranking keys."""
    sha = commit["commit"]
    pipe.zincrby("top_authors", amount, author_of(commit))
    pipe.zincrby("repo_commits", amount, repo_of(commit))
    for word in words_in(commit):
        if amount > 0:
            pipe.sadd("word:" + word, sha)
        else:
            pipe.srem("word:" + word, sha)
    if amount < 0:  # drop authors/repos whose count reached 0
        pipe.zremrangebyscore("top_authors", "-inf", 0)
        pipe.zremrangebyscore("repo_commits", "-inf", 0)


def get_commit(r, sha):
    data = r.get("commit:" + sha)
    return json.loads(data) if data else None


def ask_for_commit(r, action):
    """Show sample hashes, ask for one, and return (hash, commit)."""
    print("Sample commit hashes:")
    for sha in r.srandmember("commits", 3):
        print("  " + sha)
    sha = input("Enter the commit hash to {}: ".format(action)).strip()
    commit = get_commit(r, sha)
    if not commit:
        print("No commit found with hash {}.".format(sha))
    return sha, commit


def ask_number(prompt, default=10):
    text = input("{} [{}]: ".format(prompt, default)).strip()
    return int(text) if text.isdigit() and int(text) > 0 else default


def print_ranking(rows):
    """Print a numbered list from a Sorted Set (name, score) result."""
    for rank, (name, score) in enumerate(rows, start=1):
        print("{:<4} {:<45} {:>12,}".format(rank, name[:45], int(score)))
    if not rows:
        print("No data yet!! Load the dataset first (option 1).")


# --
# ***CREATE SECTION***
# --
def load_dataset(r):
    """Import the dataset into Redis."""
    if r.dbsize() > 0:
        if input("Redis already has data. Clear it and reload? (y/n): ").strip().lower() != "y":
            return
        r.flushdb()

    print("Importing data from {} ...".format(DATA_PATH))
    pipe = r.pipeline(transaction=False)  # sends commands in batches (much faster)

    # Commits -> one String per commit, plus search and ranking keys
    seen = set()
    for name in ("Commits.json", "Sample_Commits.json"):
        for commit in read_file(name):
            if commit["commit"] in seen:
                continue  # some commits appear in both files
            seen.add(commit["commit"])
            pipe.set("commit:" + commit["commit"], json.dumps(commit))
            pipe.sadd("commits", commit["commit"])
            index_commit(pipe, commit, 1)
            if len(seen) % 1000 == 0:
                pipe.execute()
    pipe.execute()

    # Watcher counts -> Sorted Set
    for i, repo in enumerate(read_file("Sample_Repos.json"), start=1):
        pipe.zadd("repo_watchers", {repo["repo_name"]: int(repo["watch_count"])})
        if i % 1000 == 0:
            pipe.execute()
    pipe.execute()

    # Licenses -> Hash (repo -> license) and Sorted Set (license -> count)
    for repo in read_file("Licenses.json"):
        pipe.hset("repo_licenses", repo["repo_name"], repo["license"])
        pipe.zincrby("license_counts", 1, repo["license"])
    pipe.execute()

    # Languages -> totals counted in Python first (3.3 million rows), then saved
    print("  (Languages.json is large - this takes a minute)")
    repos_per_lang, bytes_per_lang = {}, {}
    commit_repos = set(r.zrange("repo_commits", 0, -1))
    for row in read_file("Languages.json"):
        for lang in row.get("language") or []:
            name = lang["name"]
            repos_per_lang[name] = repos_per_lang.get(name, 0) + 1
            bytes_per_lang[name] = bytes_per_lang.get(name, 0) + int(lang["bytes"])
        # Remember the languages of repositories that also have commits
        if row.get("language") and row["repo_name"] in commit_repos:
            names = ", ".join(lang["name"] for lang in row["language"])
            pipe.hset("repo_languages", row["repo_name"], names)
    pipe.execute()
    if repos_per_lang:
        r.zadd("lang_repos", repos_per_lang)
        r.zadd("lang_bytes", bytes_per_lang)

    print("\nData imported successfully!! {:,} commits, {:,} repositories, {:,} languages."
          .format(r.scard("commits"), r.zcard("repo_watchers"), r.zcard("lang_repos")))


def create_commit(r):
    print("\n~ Create a Commit ~")
    repo = input("Repository name (owner/repo): ").strip()
    name = input("Author name: ").strip()
    message = input("Commit message: ").strip()
    if not (repo and name and message):
        print("All three fields are required.")
        return

    # Make a Git-style 40-character hash
    sha = hashlib.sha1("{}{}{}{}".format(repo, name, message, time.time()).encode()).hexdigest()
    commit = {"commit": sha, "author": {"name": name}, "message": message,
              "subject": message, "parent": [], "repo_name": repo}

    pipe = r.pipeline()
    pipe.set("commit:" + sha, json.dumps(commit))
    pipe.sadd("commits", sha)
    index_commit(pipe, commit, 1)
    pipe.execute()
    print("Commit created with hash: {}".format(sha))


# --
# ***READ SECTION***
# --
def read_commit(r):
    print("\n~ Read a Commit ~")
    sha, commit = ask_for_commit(r, "read")
    if commit:
        print("\n  Repository: {}".format(repo_of(commit)))
        print("  Author:     {}".format(author_of(commit)))
        print("  Message:    {}".format(" ".join((commit.get("message") or "").split())[:100]))
        if input("\nShow full JSON? (y/n): ").strip().lower() == "y":
            print(json.dumps(commit, indent=2))


# --
# ***UPDATE SECTION***
# --
def update_commit(r):
    print("\n~ Update a Commit ~")
    sha, commit = ask_for_commit(r, "update")
    if not commit:
        return
    print("1. Commit message\n2. Author name\n3. Repository name")
    choice = input("Field to update: ").strip()
    value = input("New value: ").strip()
    if choice not in ("1", "2", "3") or not value:
        print("Update cancelled.")
        return

    pipe = r.pipeline()
    index_commit(pipe, commit, -1)          # remove the old values...
    if choice == "1":
        commit["message"] = commit["subject"] = value
    elif choice == "2":
        commit["author"] = dict(commit.get("author") or {}, name=value)
    else:
        commit["repo_name"] = value
    pipe.set("commit:" + sha, json.dumps(commit))
    index_commit(pipe, commit, 1)           # ...and add the new ones
    pipe.execute()
    print("Commit updated.")


# --
# ***DELETE SECTION***
# --
def delete_commit(r):
    print("\n~ Delete a Commit ~")
    sha, commit = ask_for_commit(r, "delete")
    if not commit or input("Are you sure? (y/n): ").strip().lower() != "y":
        return

    pipe = r.pipeline()
    index_commit(pipe, commit, -1)
    pipe.delete("commit:" + sha)
    pipe.srem("commits", sha)
    pipe.execute()
    print("Commit deleted.")


# --
# ***KEY FEATURES***
# --
def language_leaderboard(r):
    """Feature 1: rank languages by number of repositories or by bytes of code."""
    print("\n~ Language Leaderboard ~")
    print("1. By number of repositories\n2. By total size of code (bytes)")
    key = "lang_bytes" if input("Choose: ").strip() == "2" else "lang_repos"
    rows = r.zrevrange(key, 0, ask_number("How many languages to show", 15) - 1, withscores=True)
    print_ranking(rows)


def repo_popularity(r):
    """Feature 2: most-watched repositories, repository lookup, license breakdown."""
    print("\n~ Repository Popularity & Licenses ~")
    print("1. Most-watched repositories\n2. Look up a repository\n3. License breakdown")
    choice = input("Choose: ").strip()

    if choice == "1":
        rows = r.zrevrange("repo_watchers", 0, ask_number("How many to show") - 1, withscores=True)
        print_ranking(rows)
    elif choice == "2":
        repo = input("Repository name (owner/repo): ").strip()
        watchers = r.zscore("repo_watchers", repo)
        print("\n  Repository: {}".format(repo))
        if watchers is not None:
            rank = r.zrevrank("repo_watchers", repo) + 1
            print("  Watchers:   {:,} (rank #{:,})".format(int(watchers), rank))
        print("  License:    {}".format(r.hget("repo_licenses", repo) or "not listed"))
        print("  Languages:  {}".format(r.hget("repo_languages", repo) or "not listed"))
        print("  Commits in dataset: {}".format(int(r.zscore("repo_commits", repo) or 0)))
    elif choice == "3":
        print_ranking(r.zrevrange("license_counts", 0, -1, withscores=True))


def commit_search(r):
    """Feature 3: keyword search on commit messages and top contributors."""
    print("\n~ Commit Search & Top Contributors ~")
    print("1. Search commit messages\n2. Most active authors\n3. Repositories with the most commits")
    choice = input("Choose: ").strip()

    if choice == "1":
        words = words_in({"message": input("Keyword(s), e.g. memory leak: ")})
        if not words:
            print("Enter at least one word with 3+ letters.")
            return
        matches = r.sinter(["word:" + w for w in words])  # commits containing ALL the words
        print("\n{:,} commits found.".format(len(matches)))
        for sha in list(matches)[:10]:
            commit = get_commit(r, sha)
            print("  {}  {:<30} {}".format(sha[:10], repo_of(commit)[:30],
                                          " ".join(commit.get("message", "").split())[:60]))
    elif choice in ("2", "3"):
        key = "top_authors" if choice == "2" else "repo_commits"
        print_ranking(r.zrevrange(key, 0, ask_number("How many to show") - 1, withscores=True))


# --
# Menus
# --
def redis_menu(r):
    actions = {"1": load_dataset, "2": create_commit, "3": read_commit, "4": update_commit,
               "5": delete_commit, "6": language_leaderboard, "7": repo_popularity,
               "8": commit_search}
    while True:
        print("\n ★ Redis({:,} commits stored)★".format(r.scard("commits")))
        print("1. Load dataset into Redis")
        print("2. Create a commit")
        print("3. Read a commit")
        print("4. Update a commit")
        print("5. Delete a commit")
        print("6. Language leaderboard")
        print("7. Repository popularity & licenses")
        print("8. Commit search & top contributors")
        print("0. Back to main menu")
        choice = input("Choose an option: ").strip()
        if choice == "0":
            return
        if choice in actions:
            actions[choice](r)
        else:
            print("Invalid option.")


def main():
    while True:
        print("\n ★ ★ ★ GitHub Archive Explorer★ ★ ★")
        print("1. Redis")
        print("2. MongoDB    (coming Week 2)")
        print("3. Cassandra  (coming Week 3)")
        print("4. Neo4j      (coming Week 4)")
        print("5. SQLite     (coming Week 5)")
        print("0. Exit")
        choice = input("Choose an option: ").strip()
        if choice == "1":
            r = connect()
            if r:
                redis_menu(r)
        elif choice in ("2", "3", "4", "5"):
            print("This database will be added in a later week.")
        elif choice == "0":
            print("\nProgram has ended!!")
            break
        else:
            print("Invalid option.")


if __name__ == "__main__":
    main()
