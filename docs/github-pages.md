# Publish the checkout experiment portfolio

This is a static website. GitHub Pages serves the root `index.html`, `portfolio-assets/`, and the screenshots in `power bi/screenshots/`. It needs no build or database connection.

1. Review and merge the portfolio pull request into the original repository’s `main` branch.
2. A repository admin opens **Settings → Pages** and selects **Deploy from a branch**.
3. Select **main** and **/ (root)**, then save.
4. Open the URL shown in Pages settings after deployment. Check the metric selector and both report pages, including the enlarged originals.

For local preview, run `python -m http.server 8000` from the repository root and open `http://localhost:8000/`.

See [GitHub’s publishing source documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).
