import typer

app = typer.Typer()


@app.command()
def install():
    """Install infra."""
    print("Installing infra")
