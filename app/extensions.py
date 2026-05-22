"""Extensiones Flask separadas para evitar imports circulares."""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
