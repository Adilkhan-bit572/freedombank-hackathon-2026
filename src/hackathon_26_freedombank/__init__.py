def main() -> None:
    """Entry point for the `hackathon-26-freedombank` script: runs the API server."""
    import uvicorn

    uvicorn.run("hackathon_26_freedombank.main:app", host="127.0.0.1", port=8000, reload=True)
