# GitHub pages generator

Generate and deploy minimalistic [website](https://adamws.github.io/) with your repositories statistics with GitHub Actions.

## Local usage

Clone this repository, install dependencies, build and serve:

```
git clone https://github.com/adamws/github-pages-generator.git && cd github-pages-generator
python -m venv .env
source .env/bin/activate
pip install -r requirements.txt
python build.py --username <<github username>>
cd output
python -m http.server
```

After that, open `http://0.0.0.0:8000/` in browser. Files from `output` directory can be
manually committed to `gh-pages` branch or your [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/about-github-pages) repository,
but it is recommended to set up automatic deployment with [GitHub Actions](https://github.com/features/actions) which will trigger
periodically, keeping your statistics up to date.

## Deployment

[todo]
