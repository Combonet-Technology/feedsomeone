import os


def get_current_branch():
    ref = os.environ.get('GITHUB_REF')
    if ref and ref.startswith('refs/heads/'):
        return ref[len('refs/heads/'):]
    return None
