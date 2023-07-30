from git import Repo


def get_current_branch():
    repo = Repo(search_parent_directories=True)
    try:
        branch = repo.active_branch.name
    except TypeError:
        # raised during PR
        commit_sha = repo.head.commit.hexsha
        branch = f'PR for {commit_sha}'
    return branch
