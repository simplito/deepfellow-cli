import typer

app = typer.Typer()


@app.command()
def install():
    """Install server."""
    print("Installing server")
