import click
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()

def init_db():
    with current_app.app_context():
        db.create_all()

@click.command('init-db')
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')

def init_app(app):
    migrate = Migrate(app, db, command='migrate')

    app.cli.add_command(init_db_command)
