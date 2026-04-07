# ============================================================
# FILE: backend/clone_repo.py
# PURPOSE: Clone a GitHub repository locally using GitPython.
#          Called by the /load_repo endpoint in app.py.
# ============================================================

import os
import re
import shutil
from git import Repo, GitCommandError


# ── Configuration ────────────────────────────────────────────
REPOS_DIR = "repos"   # folder where cloned repos are stored


def extract_repo_name(repo_url: str) -> str:
    """
    Extract the repository name from a GitHub URL.

    Examples:
        "https://github.com/user/my-repo"       → "my-repo"
        "https://github.com/user/my-repo.git"   → "my-repo"

    Args:
        repo_url: Full GitHub URL.

    Returns:
        Repository name string.

    Raises:
        ValueError: If the URL doesn't look like a GitHub repo.
    """
    # Remove trailing slashes and .git suffix
    url = repo_url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]

    # Extract the last path component as the repo name
    parts = url.split("/")
    if len(parts) < 2:
        raise ValueError(f"Invalid repository URL: {repo_url}")

    repo_name = parts[-1]

    # Validate: repo names should only contain alphanumeric, hyphens, underscores, dots
    if not re.match(r"^[a-zA-Z0-9._-]+$", repo_name):
        raise ValueError(f"Invalid repository name extracted: {repo_name}")

    return repo_name


def clone_repo(repo_url: str, force_reclone: bool = False) -> str:
    """
    Clone a GitHub repository into the repos/ folder.

    If the repo already exists locally and force_reclone is False,
    it will skip cloning and return the existing path.

    Args:
        repo_url:       Full GitHub URL (e.g. "https://github.com/user/repo").
        force_reclone:  If True, delete existing clone and re-clone.

    Returns:
        Absolute path to the cloned repository folder.

    Raises:
        ValueError:       If the URL is invalid.
        GitCommandError:  If git clone fails (e.g., repo doesn't exist).
    """
    repo_name = extract_repo_name(repo_url)
    dest_path = os.path.join(REPOS_DIR, repo_name)

    # Create repos/ directory if it doesn't exist
    os.makedirs(REPOS_DIR, exist_ok=True)

    # Handle existing clone
    if os.path.exists(dest_path):
        if force_reclone:
            print(f"[clone_repo] Removing existing clone at '{dest_path}'...")
            shutil.rmtree(dest_path)
        else:
            print(f"[clone_repo] Repository already exists at '{dest_path}'. Skipping clone.")
            return os.path.abspath(dest_path)

    # Clone the repository
    print(f"[clone_repo] Cloning '{repo_url}' into '{dest_path}'...")
    try:
        Repo.clone_from(
            repo_url,
            dest_path,
            depth=1,          # shallow clone (only latest commit — saves time & space)
            no_checkout=False,
        )
    except GitCommandError as e:
        # Clean up partial clone if it failed
        if os.path.exists(dest_path):
            shutil.rmtree(dest_path)
        raise GitCommandError(
            f"Failed to clone '{repo_url}'. "
            "Make sure the URL is correct and the repo is public."
        ) from e

    print(f"[clone_repo] Successfully cloned to '{dest_path}'.")
    return os.path.abspath(dest_path)


# ── Self-test ─────────────────────────────────────────────────
if __name__ == "__main__":
    # Quick test with a tiny public repo
    test_url = "https://github.com/octocat/Hello-World"
    try:
        path = clone_repo(test_url)
        print(f"Cloned to: {path}")
        print(f"Files: {os.listdir(path)}")
    except Exception as e:
        print(f"Error: {e}")
