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

    conn = psycopg2.connect(url)
    cur = conn.cursor()

    cur.execute('''

        -- ------------------------------------------------
        -- TABELA: igrejas
        -- Cada igreja é um tenant separado no sistema.
        -- Todos os dados são isolados por igreja.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS igrejas (
            id        SERIAL PRIMARY KEY,
            nome      TEXT NOT NULL,
            ativo     INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL
            -- ativo: 1 = ativa, 0 = desativada
            -- criado_em: data de criação no formato 'YYYY-MM-DD'
        );


        -- ------------------------------------------------
        -- TABELA: usuarios
        -- Agora cada usuário pertence a uma igreja.
        -- O super admin tem igreja_id NULL.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS usuarios (
            id        SERIAL PRIMARY KEY,
            nome      TEXT NOT NULL,
            email     TEXT UNIQUE NOT NULL,
            senha     TEXT NOT NULL,
            perfil    TEXT NOT NULL,
            igreja_id INTEGER REFERENCES igrejas(id) ON DELETE CASCADE
            -- igreja_id NULL = super admin do sistema (só você)
            -- perfil: 'superadmin', 'diretor', 'coordenador', 'secretaria', 'professor'
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
        -- Um professor pode ter várias turmas.
        -- Uma turma pode ter vários professores.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS professor_turmas (
            id           SERIAL PRIMARY KEY,
            professor_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            turma_id     INTEGER NOT NULL REFERENCES turmas(id) ON DELETE CASCADE,
            ativo        INTEGER NOT NULL DEFAULT 1
            -- ativo: 1 = professor tem acesso, 0 = acesso removido
        );


        -- ------------------------------------------------
        -- TABELA: alunos
        -- Cada aluno pertence a uma turma.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS alunos (
            id       SERIAL PRIMARY KEY,
            nome     TEXT NOT NULL,
            turma_id INTEGER NOT NULL REFERENCES turmas(id) ON DELETE CASCADE
        );


        -- ------------------------------------------------
        -- TABELA: chamadas
        -- Registro de cada chamada feita por um professor.
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
        -- Presença de cada aluno em cada chamada.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS presencas (
            id         SERIAL PRIMARY KEY,
            chamada_id INTEGER NOT NULL REFERENCES chamadas(id) ON DELETE CASCADE,
            aluno_id   INTEGER NOT NULL REFERENCES alunos(id) ON DELETE CASCADE,
            presente   INTEGER NOT NULL DEFAULT 0
        );


        -- ------------------------------------------------
        -- TABELA: questionarios
        -- Entrega de questionários por aluno.
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
            id             SERIAL PRIMARY KEY,
            nome           TEXT NOT NULL,
            preco          NUMERIC(10,2) NOT NULL DEFAULT 0,
            limite_turmas  INTEGER NOT NULL DEFAULT 5,
            limite_alunos  INTEGER NOT NULL DEFAULT 50,
            ativo          INTEGER NOT NULL DEFAULT 1
        );


        -- ------------------------------------------------
        -- TABELA: assinaturas
        -- Vínculo entre uma igreja e um plano.
        -- ------------------------------------------------
        CREATE TABLE IF NOT EXISTS assinaturas (
            id         SERIAL PRIMARY KEY,
            igreja_id  INTEGER NOT NULL REFERENCES igrejas(id) ON DELETE CASCADE,
            plano_id   INTEGER NOT NULL REFERENCES planos(id),
            status     TEXT NOT NULL DEFAULT 'ativo',
            inicio     TEXT NOT NULL,
            fim        TEXT,
            stripe_id  TEXT
            -- status: 'ativo', 'cancelado', 'inadimplente'
            -- stripe_id: ID da assinatura no Stripe para pagamentos futuros
        );

    ''')

    conn.commit()
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

     # Cria tabela igrejas se não existir
    cur.execute('''
        CREATE TABLE IF NOT EXISTS igrejas (
            id        SERIAL PRIMARY KEY,
            nome      TEXT NOT NULL,
            ativo     INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL
        );
    ''')
    
    # Adiciona a coluna horario na tabela chamadas se ainda não existir
    cur.execute('''
        ALTER TABLE chamadas
        ADD COLUMN IF NOT EXISTS horario TEXT NOT NULL DEFAULT '00:00';
    ''')
    
     # Adiciona igreja_id na tabela usuarios se não existir
    cur.execute('''
        ALTER TABLE usuarios
        ADD COLUMN IF NOT EXISTS igreja_id INTEGER REFERENCES igrejas(id) ON DELETE CASCADE;
    ''')

    # Adiciona igreja_id na tabela turmas se não existir
    cur.execute('''
        ALTER TABLE turmas
        ADD COLUMN IF NOT EXISTS igreja_id INTEGER REFERENCES igrejas(id) ON DELETE CASCADE;
    ''')
    
    # Adiciona coluna celula na tabela alunos
    cur.execute('''
        ALTER TABLE alunos
        ADD COLUMN IF NOT EXISTS celula TEXT;
    ''')
    
    # Impede turmas com mesmo nome na mesma igreja
    cur.execute('''
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'turmas_nome_igreja_unique'
            ) THEN
                ALTER TABLE turmas
                ADD CONSTRAINT turmas_nome_igreja_unique
                UNIQUE (nome, igreja_id);
            END IF;
        END$$;
    ''')

    # Impede professor designado duas vezes na mesma turma
    cur.execute('''
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'professor_turma_unique'
            ) THEN
                ALTER TABLE professor_turmas
                ADD CONSTRAINT professor_turma_unique
                UNIQUE (professor_id, turma_id);
            END IF;
        END$$;
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