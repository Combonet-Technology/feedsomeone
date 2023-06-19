from git import Repo


def get_current_branch():
    repo = Repo(search_parent_directories=True)
    branch = repo.active_branch
    return branch.name
