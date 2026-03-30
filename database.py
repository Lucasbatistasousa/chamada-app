import sqlite3
from flask import g
import os

DATABASE = 'chamada.db'

def get_db():
    from app import app
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS turmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS alunos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            turma_id INTEGER NOT NULL,
            FOREIGN KEY (turma_id) REFERENCES turmas(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS chamadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            turma_id INTEGER NOT NULL,
            data TEXT NOT NULL,
            FOREIGN KEY (turma_id) REFERENCES turmas(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS presencas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chamada_id INTEGER NOT NULL,
            aluno_id INTEGER NOT NULL,
            presente INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (chamada_id) REFERENCES chamadas(id) ON DELETE CASCADE,
            FOREIGN KEY (aluno_id) REFERENCES alunos(id) ON DELETE CASCADE
        );
        PRAGMA foreign_keys = ON;
    ''')
    conn.commit()
    conn.close()

def teardown_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
