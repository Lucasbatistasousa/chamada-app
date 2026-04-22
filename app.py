# ============================================================
# app.py
# Arquivo principal — inicializa o Flask e define as rotas.
# Uma rota é um endereço do site (ex: /login, /logout)
# e a função que roda quando alguém acessa esse endereço.
# ============================================================

from dotenv import load_dotenv
load_dotenv()
import os
# Carrega o .env ANTES de qualquer outra coisa,
# para que o DATABASE_URL já esteja disponível quando precisarmos

from database import init_db, q, teardown_db, get_db, migrate_db
from datetime import date

import csv
# Biblioteca padrão do Python para gerar arquivos CSV
# Já vem instalada, não precisa de pip install

import io
# Biblioteca padrão para criar arquivos na memória
# Em vez de salvar no disco e depois enviar, criamos
# o arquivo direto na memória e enviamos para o navegador

from flask import send_file
# send_file envia um arquivo para o navegador fazer o download
# Adicione no import do flask no topo do app.py

from flask import Flask, render_template, request, redirect, url_for, flash
# Flask          → o framework em si
# render_template → renderiza arquivos HTML da pasta templates/
# request        → acessa os dados enviados pelo formulário (POST)
# redirect       → redireciona para outra página
# url_for        → gera a URL de uma rota pelo nome da função
# flash          → envia mensagens temporárias para o HTML (ex: "Senha incorreta")

from flask_login import LoginManager, login_user, logout_user, login_required, current_user
# LoginManager   → configura o sistema de login no app
# login_user     → registra o usuário como logado na sessão
# logout_user    → remove o usuário da sessão
# login_required → decorator que bloqueia a rota se não estiver logado
# current_user   → o usuário logado no momento (acessível em qualquer rota)

from werkzeug.security import generate_password_hash, check_password_hash
# generate_password_hash → transforma a senha em hash antes de salvar no banco
#   Ex: "abc123" → "$2b$12$KIX..."
# check_password_hash    → compara a senha digitada com o hash salvo no banco
#   Nunca descriptografa — apenas verifica se batem

from database import init_db, q, teardown_db
from auth import Usuario, carregar_usuario


# --- INICIALIZAÇÃO DO APP ---

app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY')
# secret_key é usada pelo Flask para assinar os cookies de sessão.
# Sem ela, o sistema de login não funciona.
# Em produção, coloque isso no .env e leia com os.environ.get()

app.teardown_appcontext(teardown_db)
# Registra a função teardown_db para rodar ao final de cada requisição
# fechando a conexão com o banco automaticamente


# --- CONFIGURAÇÃO DO FLASK-LOGIN ---

login_manager = LoginManager()
login_manager.init_app(app)
# Conecta o LoginManager ao nosso app Flask

login_manager.login_view = 'login'
# Define para qual rota redirecionar quando alguém tentar acessar
# uma página protegida sem estar logado.
# 'login' é o nome da função da rota de login lá embaixo.

login_manager.login_message = 'Faça login para acessar essa página.'
# Mensagem que aparece quando o acesso é bloqueado


@login_manager.user_loader
def user_loader(user_id):
    # Diz ao Flask-Login como carregar o usuário a partir do ID
    # Essa função roda automaticamente em cada requisição
    return carregar_usuario(user_id)


# ============================================================
# ROTA: /login  (GET e POST)
# GET  → exibe o formulário de login
# POST → processa o formulário enviado
# ============================================================
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':
        # O usuário enviou o formulário — vamos verificar os dados

        email = request.form['email']
        # request.form acessa os campos do formulário HTML
        # 'email' deve ser o name= do input no HTML

        senha = request.form['senha']

        # Busca o usuário no banco pelo email
        usuario = q(
            'SELECT * FROM usuarios WHERE email = %s',
            (email,),
            one=True
        )

        if usuario is None:
            # Email não encontrado
            flash('Email ou senha incorretos.', 'erro')
            return redirect(url_for('login'))

        if not check_password_hash(usuario['senha'], senha):
            # O hash da senha digitada não bate com o salvo no banco
            flash('Email ou senha incorretos.', 'erro')
            return redirect(url_for('login'))

        # Tudo certo — cria o objeto Usuario e registra na sessão
        usuario_obj = Usuario(
            id     = usuario['id'],
            nome   = usuario['nome'],
            email  = usuario['email'],
            perfil = usuario['perfil']
        )
        login_user(usuario_obj)
        # A partir daqui, current_user terá os dados desse usuário

        return redirect(url_for('index'))
        # Redireciona para a página principal após o login

    # Se for GET, apenas exibe o formulário
    return render_template('login.html')


# ============================================================
# ROTA: /logout
# Encerra a sessão e redireciona para o login
# ============================================================
@app.route('/logout')
@login_required
# @login_required bloqueia a rota se não estiver logado
def logout():
    logout_user()
    return redirect(url_for('login'))


# ============================================================
# ROTA: /  (página principal)
# Protegida — só acessível com login
# ============================================================
@app.route('/')
@login_required
def index():
    return render_template('index.html')
 
# ============================================================
# ROTA: /usuarios  (GET)
# Lista todos os usuários do sistema.
# Somente diretor e coordenador podem acessar.
# ============================================================
@app.route('/usuarios')
@login_required
def usuarios():

    # Somente diretor e coordenador podem gerenciar usuários
    if current_user.perfil not in ['diretor', 'coordenador']:
        flash('Você não tem permissão para acessar essa página.', 'erro')
        return redirect(url_for('index'))

    lista_usuarios = q('SELECT * FROM usuarios ORDER BY nome')
    return render_template('usuarios.html', usuarios=lista_usuarios)


# ============================================================
# ROTA: /usuarios/criar  (POST)
# Cria um novo usuário.
# Somente diretor e coordenador podem criar.
# ============================================================
@app.route('/usuarios/criar', methods=['POST'])
@login_required
def criar_usuario():

    if current_user.perfil not in ['diretor', 'coordenador']:
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('index'))

    nome   = request.form['nome'].strip()
    email  = request.form['email'].strip()
    senha  = request.form['senha'].strip()
    perfil = request.form['perfil']

    if not nome or not email or not senha or not perfil:
        flash('Todos os campos são obrigatórios.', 'erro')
        return redirect(url_for('usuarios'))

    # Perfis válidos
    if perfil not in ['diretor', 'coordenador', 'secretaria', 'professor']:
        flash('Perfil inválido.', 'erro')
        return redirect(url_for('usuarios'))

    senha_hash = generate_password_hash(senha)

    try:
        q(
            '''INSERT INTO usuarios (nome, email, senha, perfil)
               VALUES (%s, %s, %s, %s)''',
            (nome, email, senha_hash, perfil),
            commit=True
        )
        flash(f'Usuário "{nome}" criado com sucesso!', 'sucesso')
    except:
        get_db().rollback()
        flash('Já existe um usuário com esse email.', 'erro')

    return redirect(url_for('usuarios'))


# ============================================================
# ROTA: /usuarios/<id>/deletar  (POST)
# Deleta um usuário.
# Não é possível deletar a si mesmo.
# ============================================================
@app.route('/usuarios/<int:usuario_id>/deletar', methods=['POST'])
@login_required
def deletar_usuario(usuario_id):

    if current_user.perfil not in ['diretor', 'coordenador']:
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('usuarios'))

    # Impede que o usuário delete a si mesmo
    if usuario_id == current_user.id:
        flash('Você não pode deletar sua própria conta.', 'erro')
        return redirect(url_for('usuarios'))

    q('DELETE FROM usuarios WHERE id = %s', (usuario_id,), commit=True)
    flash('Usuário removido.', 'sucesso')
    return redirect(url_for('usuarios'))
    
# ============================================================
# ROTA: /minha-conta  (GET e POST)
# Permite que qualquer usuário logado troque sua própria senha.
# ============================================================
@app.route('/minha-conta', methods=['GET', 'POST'])
@login_required
def minha_conta():

    if request.method == 'POST':
        senha_atual    = request.form['senha_atual']
        nova_senha     = request.form['nova_senha']
        confirma_senha = request.form['confirma_senha']

        # Busca o usuário no banco para verificar a senha atual
        usuario = q(
            'SELECT * FROM usuarios WHERE id = %s',
            (current_user.id,),
            one=True
        )

        # Verifica se a senha atual está correta
        if not check_password_hash(usuario['senha'], senha_atual):
            flash('Senha atual incorreta.', 'erro')
            return redirect(url_for('minha_conta'))

        # Verifica se a nova senha e a confirmação batem
        if nova_senha != confirma_senha:
            flash('A nova senha e a confirmação não conferem.', 'erro')
            return redirect(url_for('minha_conta'))

        # Verifica se a nova senha tem pelo menos 6 caracteres
        if len(nova_senha) < 6:
            flash('A nova senha deve ter pelo menos 6 caracteres.', 'erro')
            return redirect(url_for('minha_conta'))

        # Gera o hash da nova senha e salva no banco
        nova_senha_hash = generate_password_hash(nova_senha)
        q(
            'UPDATE usuarios SET senha = %s WHERE id = %s',
            (nova_senha_hash, current_user.id),
            commit=True
        )

        flash('Senha alterada com sucesso!', 'sucesso')
        return redirect(url_for('minha_conta'))

    return render_template('minha_conta.html')
    
# ============================================================
# ROTA: /turmas  (GET)
# Lista todas as turmas.
# Qualquer usuário logado pode ver.
# ============================================================
@app.route('/turmas')
@login_required
def turmas():
    todas_turmas = q('SELECT * FROM turmas ORDER BY nome')
    return render_template('turmas.html', turmas=todas_turmas)


# ============================================================
# ROTA: /turmas/criar  (POST)
# Cria uma nova turma.
# Somente diretor, coordenador e secretaria podem fazer isso.
# ============================================================
@app.route('/turmas/criar', methods=['POST'])
@login_required
def criar_turma():

    # Verifica se o usuário tem permissão
    if not current_user.pode_gerenciar_alunos():
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('turmas'))

    nome = request.form['nome'].strip()
    # .strip() remove espaços em branco no início e no fim

    if not nome:
        flash('O nome da turma não pode ser vazio.', 'erro')
        return redirect(url_for('turmas'))

    try:
        q(
            'INSERT INTO turmas (nome) VALUES (%s)',
            (nome,),
            commit=True
        )
        flash(f'Turma "{nome}" criada com sucesso!', 'sucesso')
    except:
        # Se cair aqui, provavelmente é porque a turma já existe (UNIQUE)
        q('', commit=False)  # não faz nada, só para não travar
        get_db().rollback()
        flash('Já existe uma turma com esse nome.', 'erro')

    return redirect(url_for('turmas'))


# ============================================================
# ROTA: /turmas/<id>/deletar  (POST)
# Deleta uma turma e todos os alunos dela (CASCADE).
# Somente diretor, coordenador e secretaria podem fazer isso.
# ============================================================
@app.route('/turmas/<int:turma_id>/deletar', methods=['POST'])
@login_required
def deletar_turma(turma_id):

    if not current_user.pode_gerenciar_alunos():
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('turmas'))

    q('DELETE FROM turmas WHERE id = %s', (turma_id,), commit=True)
    flash('Turma removida.', 'sucesso')
    return redirect(url_for('turmas'))


# ============================================================
# ROTA: /turmas/<id>/alunos  (GET)
# Lista os alunos de uma turma.
# Qualquer usuário logado pode ver.
# ============================================================
@app.route('/turmas/<int:turma_id>/alunos')
@login_required
def alunos(turma_id):

    turma = q(
        'SELECT * FROM turmas WHERE id = %s',
        (turma_id,),
        one=True
    )

    if turma is None:
        flash('Turma não encontrada.', 'erro')
        return redirect(url_for('turmas'))

    lista_alunos = q(
        'SELECT * FROM alunos WHERE turma_id = %s ORDER BY nome',
        (turma_id,)
    )

    return render_template('alunos.html', turma=turma, alunos=lista_alunos)


# ============================================================
# ROTA: /turmas/<id>/alunos/adicionar  (POST)
# Adiciona um aluno em uma turma.
# Somente diretor, coordenador e secretaria podem fazer isso.
# ============================================================
@app.route('/turmas/<int:turma_id>/alunos/adicionar', methods=['POST'])
@login_required
def adicionar_aluno(turma_id):

    if not current_user.pode_gerenciar_alunos():
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('alunos', turma_id=turma_id))

    nome = request.form['nome'].strip()

    if not nome:
        flash('O nome do aluno não pode ser vazio.', 'erro')
        return redirect(url_for('alunos', turma_id=turma_id))

    q(
        'INSERT INTO alunos (nome, turma_id) VALUES (%s, %s)',
        (nome, turma_id),
        commit=True
    )
    flash(f'Aluno "{nome}" adicionado!', 'sucesso')
    return redirect(url_for('alunos', turma_id=turma_id))


# ============================================================
# ROTA: /alunos/<id>/deletar  (POST)
# Remove um aluno.
# Somente diretor, coordenador e secretaria podem fazer isso.
# ============================================================
@app.route('/alunos/<int:aluno_id>/deletar', methods=['POST'])
@login_required
def deletar_aluno(aluno_id):

    # Busca o aluno para saber a qual turma pertence
    # (para redirecionar de volta para a página certa)
    aluno = q(
        'SELECT * FROM alunos WHERE id = %s',
        (aluno_id,),
        one=True
    )

    if not current_user.pode_gerenciar_alunos():
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('alunos', turma_id=aluno['turma_id']))

    q('DELETE FROM alunos WHERE id = %s', (aluno_id,), commit=True)
    flash('Aluno removido.', 'sucesso')
    return redirect(url_for('alunos', turma_id=aluno['turma_id']))

# ============================================================
# ROTA: /turmas/<id>/chamada  (GET)
# Exibe a tela de chamada com a lista de alunos da turma.
# Qualquer usuário logado pode fazer a chamada.
# ============================================================
@app.route('/turmas/<int:turma_id>/chamada')
@login_required
def chamada(turma_id):

    turma = q(
        'SELECT * FROM turmas WHERE id = %s',
        (turma_id,),
        one=True
    )

    if turma is None:
        flash('Turma não encontrada.', 'erro')
        return redirect(url_for('turmas'))

    lista_alunos = q(
        'SELECT * FROM alunos WHERE turma_id = %s ORDER BY nome',
        (turma_id,)
    )

    if not lista_alunos:
        flash('Essa turma não tem alunos cadastrados ainda.', 'erro')
        return redirect(url_for('turmas'))

    return render_template(
    'chamada.html',
    turma=turma,
    alunos=lista_alunos,
    now=date.today().strftime('%Y-%m-%d')
    # Passa a data de hoje para o HTML no formato que o input type=date entende
)


# ============================================================
# ROTA: /turmas/<id>/chamada/salvar  (POST)
# Recebe o formulário da chamada e salva no banco.
# ============================================================
@app.route('/turmas/<int:turma_id>/chamada/salvar', methods=['POST'])
@login_required
def salvar_chamada(turma_id):

    data    = request.form['data']
    horario = request.form['horario']
    # Pega o horário digitado pelo professor ex: "16:00"

    # Verifica se já existe chamada para essa turma, dia E horário
    chamada_existente = q(
        '''SELECT id FROM chamadas
           WHERE turma_id = %s AND data = %s AND horario = %s''',
        (turma_id, data, horario),
        one=True
    )

    if chamada_existente:
        q(
            'DELETE FROM presencas WHERE chamada_id = %s',
            (chamada_existente['id'],),
            commit=True
        )
        q(
            'DELETE FROM chamadas WHERE id = %s',
            (chamada_existente['id'],),
            commit=True
        )

    q(
        '''INSERT INTO chamadas (turma_id, professor_id, data, horario)
           VALUES (%s, %s, %s, %s)''',
        (turma_id, current_user.id, data, horario),
        commit=True
    )

    chamada = q(
        '''SELECT id FROM chamadas
           WHERE turma_id = %s AND data = %s AND horario = %s''',
        (turma_id, data, horario),
        one=True
    )
    chamada_id = chamada['id']

    lista_alunos = q(
        'SELECT id FROM alunos WHERE turma_id = %s',
        (turma_id,)
    )

    for aluno in lista_alunos:
        presente = 1 if str(aluno['id']) in request.form.getlist('presentes') else 0
        q(
            '''INSERT INTO presencas (chamada_id, aluno_id, presente)
               VALUES (%s, %s, %s)''',
            (chamada_id, aluno['id'], presente),
            commit=True
        )

    flash('Chamada salva com sucesso!', 'sucesso')
    return redirect(url_for('turmas'))

# ============================================================
# ROTA: /turmas/<id>/historico  (GET)
# Mostra o histórico completo de chamadas de uma turma.
# ============================================================
@app.route('/turmas/<int:turma_id>/historico')
@login_required
def historico(turma_id):

    turma = q(
        'SELECT * FROM turmas WHERE id = %s',
        (turma_id,),
        one=True
    )

    if turma is None:
        flash('Turma não encontrada.', 'erro')
        return redirect(url_for('turmas'))

    # Busca todas as chamadas da turma, da mais recente para a mais antiga
    chamadas = q(
        '''SELECT c.id, c.data, 
                  COALESCE(c.horario, '00:00') AS horario,
                  u.nome AS professor_nome
           FROM chamadas c
           JOIN usuarios u ON u.id = c.professor_id
           WHERE c.turma_id = %s
           ORDER BY c.data DESC, c.horario DESC''',
        (turma_id,)
    )
    # JOIN une as duas tabelas para pegar o nome do professor
    # em vez de só o professor_id

    # Para cada chamada, busca a presença de cada aluno
    resultado = []
    for chamada in chamadas:

        presencas = q(
            '''SELECT a.nome AS aluno_nome, p.presente
               FROM presencas p
               JOIN alunos a ON a.id = p.aluno_id
               WHERE p.chamada_id = %s
               ORDER BY a.nome''',
            (chamada['id'],)
        )

        total    = len(presencas)
        presentes = sum(1 for p in presencas if p['presente'])
        # sum() percorre a lista e conta quantos têm presente == 1

        resultado.append({
            'id'            : chamada['id'],
            'data'          : chamada['data'],
            'horario'       : chamada['horario'],
            'professor_nome': chamada['professor_nome'],
            'presencas'     : [dict(p) for p in presencas],
            'total'         : len(presencas),
            'presentes'     : sum(1 for p in presencas if p['presente']),
            'porcentagem'   : round(presentes / total * 100) if total > 0 else 0
        })

    # Monta o resumo de frequência por aluno
    # Ex: João — 8 de 10 chamadas — 80%
    alunos = q(
        'SELECT * FROM alunos WHERE turma_id = %s ORDER BY nome',
        (turma_id,)
    )

    frequencia = []
    for aluno in alunos:

        total_chamadas = len(chamadas)

        if total_chamadas == 0:
            continue
            # Se não tem nenhuma chamada ainda, pula esse aluno

        presencas_aluno = q(
            '''SELECT COUNT(*) AS total
               FROM presencas p
               JOIN chamadas c ON c.id = p.chamada_id
               WHERE p.aluno_id = %s
               AND p.presente = 1
               AND c.turma_id = %s''',
            (aluno['id'], turma_id),
            one=True
        )
        # COUNT(*) conta quantas linhas batem com o WHERE

        total_presentes = presencas_aluno['total']
        porcentagem     = round(total_presentes / total_chamadas * 100)

        frequencia.append({
            'nome'          : aluno['nome'],
            'presentes'     : total_presentes,
            'total'         : total_chamadas,
            'porcentagem'   : porcentagem
        })

    # Ordena do aluno com menor frequência para o maior
    frequencia.sort(key=lambda x: x['porcentagem'])

    return render_template(
        'historico.html',
        turma     = turma,
        resultado = resultado,
        frequencia= frequencia
    )
    
# ============================================================
# ROTA: /turmas/<id>/questionarios  (GET)
# Mostra todos os alunos da turma para o professor
# escolher quem entregou o questionário.
# ============================================================
@app.route('/turmas/<int:turma_id>/questionarios')
@login_required
def questionarios(turma_id):

    turma = q(
        'SELECT * FROM turmas WHERE id = %s',
        (turma_id,),
        one=True
    )

    if turma is None:
        flash('Turma não encontrada.', 'erro')
        return redirect(url_for('turmas'))

    lista_alunos = q(
        'SELECT * FROM alunos WHERE turma_id = %s ORDER BY nome',
        (turma_id,)
    )

    return render_template(
        'questionarios.html',
        turma=turma,
        alunos=lista_alunos,
        now=date.today().strftime('%Y-%m-%d')
    )


# ============================================================
# ROTA: /turmas/<id>/questionarios/salvar  (POST)
# Recebe o formulário e registra a entrega para
# TODOS os alunos marcados de uma só vez.
# ============================================================
@app.route('/turmas/<int:turma_id>/questionarios/salvar', methods=['POST'])
@login_required
def salvar_questionarios(turma_id):

    descricao    = request.form['descricao'].strip()
    data_entrega = request.form['data_entrega']
    alunos_ids   = request.form.getlist('alunos_ids')
    # getlist retorna uma lista com todos os IDs dos checkboxes marcados
    # Ex: ['1', '3', '5']

    if not descricao:
        flash('O nome do questionário não pode ser vazio.', 'erro')
        return redirect(url_for('questionarios', turma_id=turma_id))

    if not data_entrega:
        flash('A data de entrega é obrigatória.', 'erro')
        return redirect(url_for('questionarios', turma_id=turma_id))

    if not alunos_ids:
        flash('Marque ao menos um aluno.', 'erro')
        return redirect(url_for('questionarios', turma_id=turma_id))

    # Registra a entrega para cada aluno marcado
    for aluno_id in alunos_ids:
        q(
            '''INSERT INTO questionarios (aluno_id, professor_id, descricao, data_entrega)
               VALUES (%s, %s, %s, %s)''',
            (int(aluno_id), current_user.id, descricao, data_entrega),
            commit=True
        )

    total = len(alunos_ids)
    flash(f'{total} entrega{"s" if total > 1 else ""} registrada{"s" if total > 1 else ""}!', 'sucesso')
    return redirect(url_for('questionarios', turma_id=turma_id))

# ============================================================
# ROTA: /alunos/<id>/questionarios  (GET)
# Mostra todos os questionários entregues por um aluno.
# ============================================================
@app.route('/alunos/<int:aluno_id>/questionarios')
@login_required
def ver_questionarios_aluno(aluno_id):

    aluno = q(
        'SELECT * FROM alunos WHERE id = %s',
        (aluno_id,),
        one=True
    )

    if aluno is None:
        flash('Aluno não encontrado.', 'erro')
        return redirect(url_for('turmas'))

    questionarios_aluno = q(
        '''SELECT qe.descricao, qe.data_entrega, u.nome AS professor_nome
           FROM questionarios qe
           JOIN usuarios u ON u.id = qe.professor_id
           WHERE qe.aluno_id = %s
           ORDER BY qe.data_entrega DESC''',
        (aluno_id,)
    )
    # JOIN para pegar o nome do professor que registrou

    return render_template(
        'questionarios_aluno.html',
        aluno=aluno,
        questionarios=questionarios_aluno
    )

# ============================================================
# ROTA: /turmas/<id>/exportar/chamadas
# Gera um CSV com o histórico de chamadas da turma.
# Cada linha é um aluno, cada coluna é um dia de chamada.
# ============================================================
@app.route('/turmas/<int:turma_id>/exportar/chamadas')
@login_required
def exportar_chamadas(turma_id):

    turma = q(
        'SELECT * FROM turmas WHERE id = %s',
        (turma_id,),
        one=True
    )

    # Busca todas as chamadas da turma em ordem cronológica
    chamadas = q(
        'SELECT * FROM chamadas WHERE turma_id = %s ORDER BY data',
        (turma_id,)
    )

    # Busca todos os alunos da turma
    alunos = q(
        'SELECT * FROM alunos WHERE turma_id = %s ORDER BY nome',
        (turma_id,)
    )

    # Cria o arquivo CSV na memória
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    # Cabeçalho — primeira linha do CSV
    # Ex: Aluno | 2026-03-01 | 2026-03-02 | ... | Total Presenças | % Frequência
    cabecalho = ['Aluno']
    for chamada in chamadas:
        # Formata a data para DD/MM/YYYY
        partes = chamada['data'].split('-')
        cabecalho.append(f"{partes[2]}/{partes[1]}/{partes[0]}")
    cabecalho += ['Total Presenças', '% Frequência']
    writer.writerow(cabecalho)

    # Uma linha por aluno
    for aluno in alunos:
        linha = [aluno['nome']]
        total_presentes = 0

        for chamada in chamadas:
            presenca = q(
                '''SELECT presente FROM presencas
                   WHERE chamada_id = %s AND aluno_id = %s''',
                (chamada['id'], aluno['id']),
                one=True
            )

            if presenca is None:
                linha.append('-')
                # '-' significa que o aluno não estava cadastrado nessa chamada
            elif presenca['presente']:
                linha.append('P')
                total_presentes += 1
            else:
                linha.append('F')

        # Calcula a porcentagem de frequência
        total_chamadas = len(chamadas)
        if total_chamadas > 0:
            porcentagem = f"{round(total_presentes / total_chamadas * 100)}%"
        else:
            porcentagem = '-'

        linha += [total_presentes, porcentagem]
        writer.writerow(linha)

    # Volta para o início do arquivo antes de enviar
    output.seek(0)

    # Converte para bytes com BOM (utf-8-sig) para o Excel abrir corretamente
    conteudo = output.read().encode('utf-8-sig')

    return send_file(
        io.BytesIO(conteudo),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'chamadas_{turma["nome"]}_{date.today()}.csv'
        # download_name define o nome do arquivo que vai aparecer no download
    )


# ============================================================
# ROTA: /turmas/<id>/exportar/questionarios
# Gera um CSV com todas as entregas de questionários da turma.
# ============================================================
@app.route('/turmas/<int:turma_id>/exportar/questionarios')
@login_required
def exportar_questionarios(turma_id):

    turma = q(
        'SELECT * FROM turmas WHERE id = %s',
        (turma_id,),
        one=True
    )

    # Busca todas as entregas de questionários da turma
    entregas = q(
        '''SELECT a.nome AS aluno_nome,
                  qe.descricao,
                  qe.data_entrega,
                  u.nome AS professor_nome
           FROM questionarios qe
           JOIN alunos a   ON a.id  = qe.aluno_id
           JOIN usuarios u ON u.id  = qe.professor_id
           WHERE a.turma_id = %s
           ORDER BY qe.data_entrega DESC, a.nome''',
        (turma_id,)
    )

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    # Cabeçalho
    writer.writerow(['Aluno', 'Questionário', 'Data de Entrega', 'Registrado por'])

    for entrega in entregas:
        # Formata a data para DD/MM/YYYY
        partes = entrega['data_entrega'].split('-')
        data_formatada = f"{partes[2]}/{partes[1]}/{partes[0]}"

        writer.writerow([
            entrega['aluno_nome'],
            entrega['descricao'],
            data_formatada,
            entrega['professor_nome']
        ])

    output.seek(0)
    conteudo = output.read().encode('utf-8-sig')

    return send_file(
        io.BytesIO(conteudo),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'questionarios_{turma["nome"]}_{date.today()}.csv'
    )
    
@app.route('/criar-admin')
def criar_admin():
    senha_hash = generate_password_hash('admin123')
    try:
        q(
            '''INSERT INTO usuarios (nome, email, senha, perfil)
               VALUES (%s, %s, %s, %s)''',
            ('Administrador', 'admin@escola.com', senha_hash, 'diretor'),
            commit=True
        )
        return 'Admin criado! Email: admin@escola.com | Senha: admin123'
    except:
        get_db().rollback()
        return 'Admin já existe.'

# --- INICIALIZAÇÃO ---

init_db()
migrate_db()
if __name__ == '__main__':
    
    app.run(debug=False)