#!/usr/bin/env python3
"""PyCraft GitHub release and version tagging utility.

Usage:
    python scripts/release.py --version v1.8.0 --title "PyCraft v1.8.0 - The Bountiful Update"
    python scripts/release.py --list
"""
import argparse
import os
import subprocess
import sys


def run_cmd(cmd, check=True):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
    if check and result.returncode != 0:
        print(f"Error running command: {cmd}\n{result.stderr}", file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout.strip()


def list_tags():
    tags = run_cmd("git tag -l -n9", check=False)
    if tags:
        print("Existing Git Tags / Releases:")
        print(tags)
    else:
        print("No Git tags found.")


def generate_changelog(since_tag=None):
    if since_tag:
        cmd = f"git log {since_tag}..HEAD --oneline"
    else:
        cmd = "git log -n 25 --oneline"
    commits = run_cmd(cmd, check=False)
    lines = commits.splitlines() if commits else []
    changelog = ["### Changes in this Release:"]
    for line in lines:
        changelog.append(f"- {line}")
    return "\n".join(changelog)


def create_release(tag: str, title: str, push: bool = False, notes: str = None):
    # Ensure tag format starts with 'v'
    if not tag.startswith("v"):
        tag = f"v{tag}"

    print(f"Preparing release for tag: {tag}")
    print(f"Title: {title}")

    # Check if tag already exists
    existing = run_cmd(f"git tag -l {tag}", check=False)
    if existing:
        print(f"Tag {tag} already exists!")
        return False

    # Get changelog
    if not notes:
        # Find latest tag
        latest_tag = run_cmd("git describe --tags --abbrev=0", check=False)
        notes = generate_changelog(latest_tag if latest_tag else None)

    annotation = f"{title}\n\n{notes}"

    # Create annotated git tag
    print("Creating annotated Git tag...")
    tag_file = f"/tmp/release_tag_{tag}.txt"
    with open(tag_file, "w", encoding="utf-8") as f:
        f.write(annotation)

    run_cmd(f"git tag -a {tag} -F {tag_file}")
    if os.path.exists(tag_file):
        os.remove(tag_file)
    print(f"Successfully created git tag: {tag}")

    # Check if gh CLI is available for creating a GitHub release
    gh_available = run_cmd("which gh", check=False)
    if gh_available:
        print("GitHub CLI (gh) detected. Creating GitHub Release...")
        cmd = f"gh release create {tag} --title \"{title}\" --notes \"{notes}\""
        if not push:
            print(f"Run to publish release: {cmd}")
        else:
            run_cmd(cmd, check=False)
            print(f"Published GitHub Release for {tag}!")

    if push:
        print(f"Pushing tag {tag} to remote...")
        run_cmd(f"git push origin {tag}")
        print("Pushed successfully!")
    else:
        print(f"To push this release to GitHub, run:\n    git push origin {tag}")

    return True


def main():
    parser = argparse.ArgumentParser(description="PyCraft Release Manager")
    parser.add_argument("--version", "-v", help="Release version tag (e.g., 1.8.0 or v1.8.0)")
    parser.add_argument("--title", "-t", help="Release title")
    parser.add_argument("--notes", "-n", help="Custom release notes")
    parser.add_argument("--push", "-p", action="store_true", help="Push tag and release to origin")
    parser.add_argument("--list", "-l", action="store_true", help="List existing tags")

    args = parser.parse_args()

    if args.list:
        list_tags()
        return

    if not args.version:
        parser.print_help()
        sys.exit(1)

    title = args.title or f"PyCraft {args.version}"
    create_release(args.version, title, push=args.push, notes=args.notes)


if __name__ == "__main__":
    main()
