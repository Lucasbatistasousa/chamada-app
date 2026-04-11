# ============================================================
# database.py
# Responsável por TUDO relacionado ao banco de dados:
# - Conectar ao PostgreSQL
# - Criar as tabelas
# - Executar queries (consultas e comandos)
# ============================================================


# --- IMPORTAÇÕES ---
# Essas são bibliotecas que precisamos usar

import psycopg2
# psycopg2 é o "driver" que conecta Python ao PostgreSQL.
# Sem ele, o Python não sabe como falar com o banco.

import psycopg2.extras
# Parte extra do psycopg2 que nos permite receber os resultados
# do banco como dicionários (ex: aluno['nome'])
# em vez de tuplas (ex: aluno[0]), que são mais difíceis de ler.

from flask import g
# O 'g' é um objeto especial do Flask.
# Ele existe apenas durante uma requisição (quando alguém abre uma página).
# Usamos ele para guardar a conexão com o banco e não precisar
# abrir uma conexão nova a cada função.

import os
# Biblioteca padrão do Python para acessar o sistema operacional.
# Usamos aqui para ler variáveis de ambiente (como a URL do banco).


# --- CONFIGURAÇÃO ---

DATABASE_URL = os.environ.get('DATABASE_URL')
# os.environ.get('DATABASE_URL') lê uma variável de ambiente chamada DATABASE_URL.
# Variáveis de ambiente são configurações que ficam FORA do código,
# por segurança — assim você não expõe senha no GitHub.
#
# Localmente, você vai criar um arquivo .env com:
#   DATABASE_URL=postgresql://usuario:senha@localhost:5432/nome_do_banco
#
# No Render (quando for ao ar), você configura isso no painel deles.


# ============================================================
# FUNÇÃO: get_db()
# ============================================================
def get_db():
    """
    Retorna a conexão ativa com o banco de dados.

    Em vez de abrir uma conexão nova a cada vez que precisamos
    do banco, verificamos se já existe uma conexão nesta
    requisição (guardada no 'g'). Se sim, reutilizamos.
    Se não, criamos uma nova.
    """

    # Tenta buscar uma conexão já existente no 'g'
    # getattr(objeto, 'nome', valor_padrão) — se não existir, retorna None
    db = getattr(g, '_database', None)

    if db is None:
        # Não existe conexão ainda — vamos criar uma

        url = DATABASE_URL

        # O Render.com fornece URLs que começam com "postgres://"
        # mas o psycopg2 só aceita "postgresql://"
        # Então fazemos essa correção se necessário:
        if url and url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
            # O '1' no final significa: substitua só a primeira ocorrência

        # Abre a conexão com o banco usando a URL
        db = psycopg2.connect(
            url,
            cursor_factory=psycopg2.extras.RealDictCursor
            # RealDictCursor faz os resultados virem como dicionários:
            # Ex: usuario['nome'] em vez de usuario[0]
        )

        # Guarda a conexão no 'g' para reutilizar nesta requisição
        g._database = db

    return db


# ============================================================
# FUNÇÃO: q() — abreviação de "query"
# ============================================================
def q(sql, params=(), one=False, commit=False):
    """
    Função auxiliar para executar qualquer comando no banco.
    Criamos ela para não repetir as mesmas 4 linhas em todo lugar.

    Parâmetros:
    - sql    : o comando SQL a executar (ex: 'SELECT * FROM alunos')
    - params : os valores que substituem os %s no SQL
               NUNCA coloque valores direto no SQL — use %s + params
               Isso protege contra "SQL Injection" (um tipo de ataque hacker)
    - one    : True = quero só 1 resultado | False = quero todos
    - commit : True = estou gravando algo no banco (INSERT/UPDATE/DELETE)
               False = estou apenas lendo (SELECT)

    Exemplos de uso:
        # Buscar todos os alunos:
        alunos = q('SELECT * FROM alunos')

        # Buscar um aluno pelo id:
        aluno = q('SELECT * FROM alunos WHERE id = %s', (3,), one=True)

        # Inserir um aluno:
        q('INSERT INTO alunos (nome) VALUES (%s)', ('João',), commit=True)
    """

    conn = get_db()         # pega a conexão ativa
    cur = conn.cursor()     # cursor é o "executor" de comandos dentro da conexão

    cur.execute(sql, params)
    # Executa o SQL substituindo os %s pelos valores em params com segurança

    if commit:
        # Se é uma operação de escrita (INSERT, UPDATE, DELETE),
        # precisamos confirmar com commit() para gravar de verdade no banco
        conn.commit()
        cur.close()
        return None         # Operações de escrita não retornam dados

    # Se é leitura (SELECT), buscamos os resultados:
    if one:
        result = cur.fetchone()   # retorna apenas 1 linha (ou None se não achar)
    else:
        result = cur.fetchall()   # retorna todas as linhas como uma lista

    cur.close()     # fecha o cursor para liberar memória
    return result


# ============================================================
# FUNÇÃO: init_db()
# Cria todas as tabelas do banco se ainda não existirem.
# Rodamos essa função UMA VEZ ao iniciar o app.
# ============================================================
def init_db():
    """
    Cria a estrutura completa do banco de dados.
    O comando 'CREATE TABLE IF NOT EXISTS' garante que
    se a tabela já existir, não vai dar erro nem apagar os dados.
    """

    url = DATABASE_URL
    if url and url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)

    # Aqui abrimos uma conexão direta (sem usar o 'g')
    # porque init_db() roda fora do contexto de uma requisição Flask
    conn = psycopg2.connect(url)
    cur = conn.cursor()

    cur.execute('''

        -- ------------------------------------------------
        -- TABELA: usuarios
        -- Guarda todos os funcionários que usam o sistema.
        -- Cada um tem um perfil que define o que pode fazer.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS usuarios (
            id       SERIAL PRIMARY KEY,
            -- SERIAL = número que cresce automaticamente (1, 2, 3...)
            -- PRIMARY KEY = identificador único de cada linha

            nome     TEXT NOT NULL,
            -- TEXT = texto de qualquer tamanho
            -- NOT NULL = campo obrigatório, não pode ficar vazio

            email    TEXT UNIQUE NOT NULL,
            -- UNIQUE = não pode existir dois usuários com o mesmo email

            senha    TEXT NOT NULL,
            -- ATENÇÃO: nunca vamos guardar a senha pura aqui.
            -- Vamos guardar o HASH da senha (uma versão embaralhada).
            -- Ex: "abc123" vira "$2b$12$KIX..." usando bcrypt

            perfil   TEXT NOT NULL
            -- Valores possíveis: 'diretor', 'coordenador', 'secretaria', 'professor'
            -- O perfil controla o que cada usuário pode fazer no sistema
        );


        -- ------------------------------------------------
        -- TABELA: turmas
        -- Representa cada turma da escola (ex: 3º Ano A).
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS turmas (
            id   SERIAL PRIMARY KEY,
            nome TEXT UNIQUE NOT NULL
            -- UNIQUE aqui impede criar duas turmas com o mesmo nome
        );


        -- ------------------------------------------------
        -- TABELA: alunos
        -- Cada aluno pertence a uma turma.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS alunos (
            id       SERIAL PRIMARY KEY,
            nome     TEXT NOT NULL,
            turma_id INTEGER NOT NULL REFERENCES turmas(id) ON DELETE CASCADE
            -- REFERENCES turmas(id) = chave estrangeira:
            --   o turma_id aqui deve existir na tabela turmas.
            --   Isso garante que não existe aluno sem turma válida.
            --
            -- ON DELETE CASCADE = se a turma for deletada,
            --   todos os alunos dela são deletados automaticamente.
        );


        -- ------------------------------------------------
        -- TABELA: chamadas
        -- Registra cada vez que um professor fez a chamada.
        -- Uma chamada = um professor + uma turma + um dia.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS chamadas (
            id           SERIAL PRIMARY KEY,
            turma_id     INTEGER NOT NULL REFERENCES turmas(id) ON DELETE CASCADE,
            professor_id INTEGER NOT NULL REFERENCES usuarios(id),
            -- Registramos QUEM fez a chamada
            data         TEXT NOT NULL
            -- Guardamos a data como texto no formato 'YYYY-MM-DD'
            -- Ex: '2026-03-30'
        );


        -- ------------------------------------------------
        -- TABELA: presencas
        -- Guarda a presença de CADA aluno em CADA chamada.
        -- É aqui que sabemos se o aluno estava presente ou não.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS presencas (
            id          SERIAL PRIMARY KEY,
            chamada_id  INTEGER NOT NULL REFERENCES chamadas(id) ON DELETE CASCADE,
            aluno_id    INTEGER NOT NULL REFERENCES alunos(id) ON DELETE CASCADE,
            presente    INTEGER NOT NULL DEFAULT 0
            -- DEFAULT 0 = por padrão o aluno começa como ausente (0 = falta, 1 = presente)
        );


        -- ------------------------------------------------
        -- TABELA: questionarios
        -- Registra quando um aluno entregou um questionário.
        -- O professor lança a entrega com a data.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS questionarios (
            id           SERIAL PRIMARY KEY,
            aluno_id     INTEGER NOT NULL REFERENCES alunos(id) ON DELETE CASCADE,
            professor_id INTEGER NOT NULL REFERENCES usuarios(id),
            -- Registramos QUAL professor recebeu o questionário
            descricao    TEXT NOT NULL,
            -- Nome ou título do questionário. Ex: 'Questionário Cap. 3 - Matemática'
            data_entrega TEXT NOT NULL
            -- Data em que o aluno entregou. Ex: '2026-03-28'
        );

    ''')

    conn.commit()   # confirma a criação das tabelas no banco
    cur.close()
    conn.close()

    print('✅ Banco de dados inicializado com sucesso!')


def migrate_db():
    """
    Adiciona colunas novas em tabelas que já existem.
    Rodamos isso separado do init_db() para não perder dados.
    """
    url = DATABASE_URL
    if url and url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    conn = psycopg2.connect(url)
    cur = conn.cursor()

    # Adiciona a coluna horario na tabela chamadas se ainda não existir
    cur.execute('''
        ALTER TABLE chamadas
        ADD COLUMN IF NOT EXISTS horario TEXT NOT NULL DEFAULT '00:00';
    ''')

    conn.commit()
    cur.close()
    conn.close()
    print('✅ Migração executada com sucesso!')

# ============================================================
# FUNÇÃO: teardown_db()
# Fecha a conexão com o banco ao final de cada requisição.
# Flask chama essa função automaticamente — você não precisa
# chamar ela em nenhum lugar do seu código.
# ============================================================
def teardown_db(exception):
    """
    Encerra a conexão com o banco ao fim de cada requisição.
    O parâmetro 'exception' é exigido pelo Flask — ele passa
    qualquer erro que tenha ocorrido, mas aqui não usamos.
    """
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()