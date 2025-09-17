from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "github"
commits_tree_table = "commit_nodes1"
prs_table = "pr_commit_data"
forks_table = "repo_with_forks"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
commits_tree = db[commits_tree_table]
prs = db[prs_table]
forks = db[forks_table]


def analyze():
    for repo in forks.find():
        contributions_gte_10 = set()
        contributions_lt_10 = set()
        developers = set()
        repo_id = repo['repo_id']
        fork_list = repo['forks']
        fork_set = set()
        for temp in fork_list:
            if temp['stars']>=10:
                fork_set.add(temp['repo_id'])
        for temp in commits_tree.find({'repo': repo_id}):
            for commit in temp['commits']:
                if repo_id not in temp['commits'][commit]['from_repo']:
                    for temp_fork in temp['commits'][commit]['from_repo']:
                        developers.add(temp_fork)
        for temp in prs.find({'Repo': repo_id}):
            if temp['External Repo'] in fork_set:
                contributions_gte_10.add(temp['External Repo'])
            else:
                contributions_lt_10.add(temp['External Repo'])
        print(repo_id,len(fork_set), len(contributions_gte_10), len(contributions_lt_10), len(developers),len(contributions_gte_10 & contributions_lt_10 & developers), len(fork_set - contributions_gte_10 - developers))


if __name__ == "__main__":
    analyze()