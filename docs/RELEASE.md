# Release checklist

Steps to publish a new version of `aidd-cli` to PyPI.

1. **Bump the version** in `pyproject.toml` (`[project].version`).

2. **Run the tests**

   ```
   python -m unittest discover -s tests -v
   ```

3. **Build the distributions**

   ```
   python -m build
   ```

   This produces `dist/aidd_cli-<version>-py3-none-any.whl` and
   `dist/aidd_cli-<version>.tar.gz`. Install `build` first if needed:
   `python -m pip install build`.

4. **Check the package metadata**

   ```
   python -m twine check dist/*
   ```

   Fix anything it flags (missing/invalid metadata, README that won't render on
   PyPI, etc.) before continuing. Install `twine` first if needed:
   `python -m pip install twine`.

5. **Upload to PyPI**

   ```
   python -m twine upload dist/*
   ```

   This needs PyPI credentials configured beforehand, via one of:
   - a `~/.pypirc` file with an API token, or
   - the `TWINE_USERNAME` / `TWINE_PASSWORD` environment variables
     (use `__token__` as the username and a PyPI API token as the password).

   No token is stored in this repo — only the maintainer with a PyPI account
   for this project can run this step.

6. **Tag the release in git**

   ```
   git tag v<version>
   git push --tags
   ```

Steps 2–4 should also be run for every release candidate before step 5, since
step 5 is irreversible (PyPI does not allow re-uploading the same version).
