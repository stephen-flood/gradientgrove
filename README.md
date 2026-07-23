# Example Package

[Python Packaging User Guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/)

1. Directory structure
2. `pyproject.toml`
3. License
4. Generate distribution archives

    In the directory containing `pyproject.toml` run 
    ```
    python -m pip install --upgrade build
    python -m build
    ```

5. Upload archives 

    ```
    python -m pip install --upgrade twine
    python3 -m twine upload dist/*
    ```
    