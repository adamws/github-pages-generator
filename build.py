import argparse
import os
import shutil
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from PIL import Image
from requests_cache import CachedSession


GITHUB_API = "https://api.github.com"
session = CachedSession()


def session_get(endpoint: str):
    response = session.get(endpoint)
    if response.status_code != 200:
        print(f"Request {endpoint} failed, aborting")
        exit()
    return response


def create_favicon(image_path: Path):
    image = Image.open(image_path)
    image.save(image_path.parent / "favicon.ico", format="ICO")


def get_avatar(user: str, output_directory: Path):
    endpoint = f"{GITHUB_API}/users/{user}"
    response = session_get(endpoint)

    user_data = response.json()
    avatar_url = user_data["avatar_url"]
    response = session_get(avatar_url)
    avatar_path = output_directory / "avatar.png"
    with open(avatar_path, "wb") as f:
        f.write(response.content)
    create_favicon(avatar_path)


def get_projects_data(user):
    endpoint = f"{GITHUB_API}/users/{user}/repos"
    response = session_get(endpoint)

    projects = response.json()
    projects = [x for x in projects if not x["fork"]]
    projects = sorted(projects, key=lambda x: int(x["stargazers_count"]), reverse=True)

    for i, project in enumerate(projects):
        # get languages statistcs
        response = session_get(project["languages_url"])
        languages = response.json()
        sum_of_bytes = sum(languages.values())
        for language, bytes_of_code in languages.items():
            percentage = round(bytes_of_code / sum_of_bytes * 100, 1)
            languages[language] = f"{percentage:g}"
        if not languages:
            languages = {"Other": "100"}
        languages_filtered = {}
        for language, percentage in languages.items():
            if percentage != "0":
                languages_filtered[language] = percentage

        project["languages"] = languages_filtered

        # simplify time
        time = project["updated_at"]
        project["updated_at"] = time[0 : time.find("T")]

        projects[i] = project

    return projects


def render(projects, output_directory: Path):
    env = Environment(
        loader=FileSystemLoader("templates"), autoescape=select_autoescape()
    )
    template = env.get_template("index.html")
    page = template.render(projects=projects)

    with open(str(output_directory / "index.html"), "w") as f:
        for line in page.splitlines():
            f.write(line.strip())

    template = env.get_template("style.css")
    template.stream().dump(str(output_directory / "style.css"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Static site generator for GitHub Pages"
    )
    parser.add_argument("-u", "--username", required=True, help="GitHub username")

    args = parser.parse_args()

    user = args.username
    output_directory = Path("output")

    shutil.rmtree(output_directory, ignore_errors=True)
    os.mkdir(output_directory)

    get_avatar(user, output_directory)
    projects = get_projects_data(user)
    render(projects, output_directory)