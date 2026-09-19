# AfterVolt Content Studio — staging branch

This branch is a **draft** of a local content editor for AfterVolt Records. The live website stays on `main` until the changes are deliberately merged. Never put passwords or tokens in this public repository.

## What it does

The site reads `content.json` to show the label description, artist roster and releases. `editor.py` runs a private editor at `http://127.0.0.1:8765/editor` on your own computer. Save draft modifies the local JSON; Publish creates and pushes a Git commit to `main`. GitHub Pages then deploys it. It cannot run as an admin interface on GitHub Pages: **do not expose port 8765 to the Internet**.

## Before using it

Review `index.html`, `content.json`, and `editor.py` on this branch. When you are happy with the changes, merge this branch into `main` through a pull request. This replaces the current placeholder release cards with a coming-soon message until actual releases are added. Keep the existing `CNAME` and DNS settings untouched.

On Linux Mint, install Git, Python 3 and GitHub CLI if necessary:

```bash
sudo apt update
sudo apt install git python3 gh
```

Give the editor's GitHub user write permission to `Neurvs/AfterVoltRecords`; don't share personal login credentials. Run `gh auth login` and `gh auth setup-git` with that user's own account. Clone the existing repository, **after merging the branch**:

```bash
git clone https://github.com/Neurvs/AfterVoltRecords.git
cd AfterVoltRecords
python3 editor.py
```

If the browser does not open automatically, visit `http://127.0.0.1:8765/editor`. Fill in the fields, click **Save draft**, inspect the local preview, then click **Publish to website**. The publishing function only runs on the `main` branch and refuses to push if GitHub has newer commits. It commits only `content.json`.

You may need to configure a Git identity once using `git config user.name "AfterVolt Records"` and `git config user.email "YOUR_GITHUB_COMMIT_EMAIL"` (use a verified email or GitHub no-reply address for your own account).

## Artwork and safety

This version does not upload artwork. Put covers in the repo's `assets/` folder and use a relative path such as `assets/cover.jpg`, or enter a public HTTPS image URL. Don't upload copyrighted images without permission. Do not store credentials in content fields. Only one person should edit at a time. If the editor reports newer commits, save a backup of local drafts before pulling and resolving conflicts.
