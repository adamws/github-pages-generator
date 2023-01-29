import argparse
import json
import os
import requests
import shutil
import sys
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from PIL import Image
from requests_cache import CachedSession

user = os.environ.get("GITHUB_USER", None)
token = os.environ.get("PERSONAL_ACCESS_TOKEN", None)
github_token = os.environ.get("GITHUB_TOKEN", None)

default_colorscheme = (
    os.path.abspath(os.path.dirname(__file__)) + "/colorschemes/default.json"
)

GITHUB_API = "https://api.github.com"

# there is something wrong with request cache when running in container
if os.environ.get("GITHUB_ACTIONS", None):
    session = requests.Session()
else:
    session = CachedSession()


def session_get(endpoint: str):
    if user and token:
        response = session.get(endpoint, auth=(user, token))
    elif github_token:
        headers = {"authorization": f"Bearer {github_token}"}
        response = session.get(endpoint, headers=headers)
    else:
        response = session.get(endpoint)

    if response.status_code != 200:
        print(f"Status code: {response.status_code}, Reason: {response.reason}")
        sys.exit(f"Request {endpoint} failed, aborting")
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
    img = Image.open(avatar_path)
    img = img.resize((84, 84))
    img.save(avatar_path)
    create_favicon(avatar_path)


def get_projects_data(user):
    projects = []
    page = 1

    while True:
        endpoint = f"{GITHUB_API}/users/{user}/repos?page={page}"
        response = session_get(endpoint).json()
        if response:
            projects.extend(response)
            page += 1
        else:
            break

    for i, project in enumerate(projects):
        # get languages statistcs
        response = session_get(project["languages_url"])
        languages = response.json()
        project["languages"] = languages
        projects[i] = project

    return projects


def process_projects_data(projects, ignore_list):
    projects = [x for x in projects if not x["fork"] if x["name"] not in ignore_list]
    projects = sorted(projects, key=lambda x: int(x["stargazers_count"]), reverse=True)

    for i, project in enumerate(projects):
        languages = project["languages"]
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
        time = project["pushed_at"]
        project["pushed_at"] = time[0 : time.find("T")]

        projects[i] = project

    return projects


def render(projects, colors, header, footer, output_directory: Path):
    env = Environment(
        loader=FileSystemLoader(
            os.path.abspath(os.path.dirname(__file__)) + "/templates"
        ),
        autoescape=select_autoescape(),
    )
    template = env.get_template("index.html")
    page = template.render(projects=projects, header=header, footer=footer)

    with open(str(output_directory / "index.html"), "w") as f:
        for line in page.splitlines():
            f.write(line.strip())

    template = env.get_template("style.css")
    template.stream(colors=colors).dump(str(output_directory / "style.css"))


def parse_action_arguments():
    global github_token
    github_token = os.environ.get("INPUT_GITHUB_TOKEN", None)

    username = os.environ.get("INPUT_USERNAME", None)
    colorscheme = default_colorscheme
    colorscheme_values = os.environ.get("INPUT_COLORSCHEME", None)
    if colorscheme_values:
        keys = [
            "background",
            "projects-background",
            "project-card",
            "text",
            "text-link",
        ]
        colors = [s.strip() for s in colorscheme_values.split(",")]
        if len(colors) != len(keys):
            raise ValueError("Illegal colorscheme")
        colors = dict(zip(keys, colors))
        with open("/tmp/colorscheme.json", "w") as fp:
            json.dump(colors, fp)
        colorscheme = "/tmp/colorscheme.json"

    output = os.environ.get("INPUT_OUTPUT_DIR", "./output")
    ignore = os.environ.get("INPUT_IGNORE_REPOSITORIES", None)
    skip_header = os.environ.get("INPUT_SKIP_HEADER", False)
    skip_footer = os.environ.get("INPUT_SKIP_FOOTER", False)

    return argparse.Namespace(
        username=username,
        colorscheme=colorscheme,
        output=output,
        ignore=ignore,
        skip_header=skip_header,
        skip_footer=skip_footer,
    )


def parse_cli():
    parser = argparse.ArgumentParser(
        description="Static site generator for GitHub Pages"
    )
    parser.add_argument("-u", "--username", required=True, help="GitHub username")
    parser.add_argument(
        "--colorscheme",
        type=str,
        default=default_colorscheme,
        help="Colorscheme file path",
    )
    parser.add_argument(
        "--output", type=Path, default="./output", help="Output directory"
    )
    parser.add_argument(
        "--ignore", type=str, help="Comma separated list of repositories to ignore"
    )
    parser.add_argument("--skip-header", action="store_true", help="Turns off header")
    parser.add_argument("--skip-footer", action="store_true", help="Turns off footer")
    return parser.parse_args()


if __name__ == "__main__":
    if os.environ.get("GITHUB_ACTIONS", None):
        args = parse_action_arguments()
    else:
        args = parse_cli()

    user = args.username
    ignore = args.ignore
    if ignore:
        ignore = [s.strip() for s in ignore.split(",")]
    else:
        # nothing to ignore
        ignore = []

    with open(args.colorscheme, "r") as f:
        colors = json.loads(f.read())

    header = not args.skip_header
    footer = not args.skip_footer

    output_directory = Path(args.output)

    shutil.rmtree(output_directory, ignore_errors=True)
    os.makedirs(output_directory, exist_ok=True)

    if header:
        get_avatar(user, output_directory)
    projects = get_projects_data(user)
    projects = process_projects_data(projects, ignore)
    render(projects, colors, header, footer, output_directory)

    # fix output permission if running as root inside dockerized GitHub action
    if os.environ.get("GITHUB_ACTIONS", None):
        shutil.chown(output_directory, user=1001, group=1001)
