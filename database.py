# ============================================================
# database.py
# Responsável por TUDO relacionado ao banco de dados:
# - Conectar ao PostgreSQL/Supabase
# - Criar as tabelas
# - Executar queries
# ============================================================

import psycopg2
import psycopg2.extras
from flask import g
import os

DATABASE_URL = os.environ.get('DATABASE_URL')


def get_db():
    """
    Retorna a conexão ativa com o banco para a requisição atual.
    Reutiliza a conexão existente no 'g' se já houver uma.
    """
    db = getattr(g, '_database', None)
    if db is None:
        url = DATABASE_URL
        if url and url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        db = g._database = psycopg2.connect(
            url,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    return db


def q(sql, params=(), one=False, commit=False):
    """
    Função auxiliar para executar queries sem repetir código.
    - sql    : o comando SQL
    - params : valores que substituem os %s (proteção contra SQL Injection)
    - one    : True = retorna só 1 linha | False = retorna todas
    - commit : True = grava no banco (INSERT, UPDATE, DELETE)
    """
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(sql, params)
    if commit:
        conn.commit()
        cur.close()
        return None
    result = cur.fetchone() if one else cur.fetchall()
    cur.close()
    return result


def init_db():
    """
    Cria todas as tabelas do banco se ainda não existirem.
    """
    url = DATABASE_URL
    if url and url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    conn = psycopg2.connect(url)
    cur  = conn.cursor()

    cur.execute('''

        -- ------------------------------------------------
        -- TABELA: igrejas
        -- Cada igreja é um tenant separado no sistema.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS igrejas (
            id        SERIAL PRIMARY KEY,
            nome      TEXT NOT NULL,
            ativo     INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL
        );


        -- ------------------------------------------------
        -- TABELA: usuarios
        -- Usuários do sistema.
        -- O perfil aqui só é usado para o superadmin.
        -- Os demais perfis ficam em usuario_igrejas.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS usuarios (
            id     SERIAL PRIMARY KEY,
            nome   TEXT NOT NULL,
            email  TEXT UNIQUE NOT NULL,
            senha  TEXT NOT NULL,
            perfil TEXT NOT NULL DEFAULT 'usuario'
            -- perfil: 'superadmin' ou 'usuario'
            -- o perfil dentro de cada igreja fica em usuario_igrejas
        );


        -- ------------------------------------------------
        -- TABELA: usuario_igrejas
        -- Relaciona usuários com igrejas.
        -- Um usuário pode pertencer a várias igrejas
        -- com perfis diferentes em cada uma.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS usuario_igrejas (
            id         SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            igreja_id  INTEGER NOT NULL REFERENCES igrejas(id) ON DELETE CASCADE,
            perfil     TEXT NOT NULL,
            ativo      INTEGER NOT NULL DEFAULT 1,
            UNIQUE (usuario_id, igreja_id)
            -- Um usuário só pode ter um vínculo por igreja
            -- O perfil pode ser: 'diretor', 'coordenador', 'secretaria', 'professor'
        );


        -- ------------------------------------------------
        -- TABELA: turmas
        -- Cada turma pertence a uma igreja.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS turmas (
            id        SERIAL PRIMARY KEY,
            nome      TEXT NOT NULL,
            igreja_id INTEGER NOT NULL REFERENCES igrejas(id) ON DELETE CASCADE
        );


        -- ------------------------------------------------
        -- TABELA: professor_turmas
        -- Controla quais turmas cada professor pode acessar.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS professor_turmas (
            id           SERIAL PRIMARY KEY,
            professor_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            turma_id     INTEGER NOT NULL REFERENCES turmas(id) ON DELETE CASCADE,
            ativo        INTEGER NOT NULL DEFAULT 1,
            UNIQUE (professor_id, turma_id)
        );


        -- ------------------------------------------------
        -- TABELA: alunos
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS alunos (
            id       SERIAL PRIMARY KEY,
            nome     TEXT NOT NULL,
            turma_id INTEGER NOT NULL REFERENCES turmas(id) ON DELETE CASCADE,
            celula   TEXT
        );


        -- ------------------------------------------------
        -- TABELA: chamadas
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS chamadas (
            id           SERIAL PRIMARY KEY,
            turma_id     INTEGER NOT NULL REFERENCES turmas(id) ON DELETE CASCADE,
            professor_id INTEGER NOT NULL REFERENCES usuarios(id),
            data         TEXT NOT NULL,
            horario      TEXT NOT NULL DEFAULT '00:00'
        );


        -- ------------------------------------------------
        -- TABELA: presencas
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS presencas (
            id         SERIAL PRIMARY KEY,
            chamada_id INTEGER NOT NULL REFERENCES chamadas(id) ON DELETE CASCADE,
            aluno_id   INTEGER NOT NULL REFERENCES alunos(id) ON DELETE CASCADE,
            presente   INTEGER NOT NULL DEFAULT 0
        );


        -- ------------------------------------------------
        -- TABELA: questionarios
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS questionarios (
            id           SERIAL PRIMARY KEY,
            aluno_id     INTEGER NOT NULL REFERENCES alunos(id) ON DELETE CASCADE,
            professor_id INTEGER NOT NULL REFERENCES usuarios(id),
            descricao    TEXT NOT NULL,
            data_entrega TEXT NOT NULL
        );


        -- ------------------------------------------------
        -- TABELA: planos
        -- Planos disponíveis no SaaS.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS planos (
            id            SERIAL PRIMARY KEY,
            nome          TEXT NOT NULL,
            preco         NUMERIC(10,2) NOT NULL DEFAULT 0,
            limite_turmas INTEGER NOT NULL DEFAULT 5,
            limite_alunos INTEGER NOT NULL DEFAULT 50,
            ativo         INTEGER NOT NULL DEFAULT 1
        );


        -- ------------------------------------------------
        -- TABELA: assinaturas
        -- Vínculo entre uma igreja e um plano.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS assinaturas (
            id        SERIAL PRIMARY KEY,
            igreja_id INTEGER NOT NULL REFERENCES igrejas(id) ON DELETE CASCADE,
            plano_id  INTEGER NOT NULL REFERENCES planos(id),
            status    TEXT NOT NULL DEFAULT 'ativo',
            inicio    TEXT NOT NULL,
            fim       TEXT,
            stripe_id TEXT
        );

    ''')

    conn.commit()
    cur.close()
    conn.close()
    print('✅ Banco de dados inicializado com sucesso!')


def teardown_db(exception):
    """Fecha a conexão ao final de cada requisição."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()