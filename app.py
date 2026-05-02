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

from database import init_db, q, teardown_db, get_db
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

from flask import Flask, render_template, request, redirect, url_for, flash, session
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

from database import init_db, q, teardown_db, get_db
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
    # Busca o ID da igreja salvo na sessão
    igreja_id = session.get('igreja_atual')
    return carregar_usuario(user_id, igreja_id)

# ============================================================
# ROTA: /igrejas  (GET)
# Lista todas as igrejas do sistema.
# Somente superadmin pode acessar.
# ============================================================
@app.route('/igrejas')
@login_required
def igrejas():

    if not current_user.pode_gerenciar_igrejas():
        flash('Você não tem permissão para acessar essa página.', 'erro')
        return redirect(url_for('index'))

    lista_igrejas = q('''
        SELECT i.*, u.nome AS diretor_nome
        FROM igrejas i
        LEFT JOIN usuarios u ON u.igreja_id = i.id AND u.perfil = 'diretor'
        ORDER BY i.nome
    ''')

    return render_template('igrejas.html', igrejas=lista_igrejas)


# ============================================================
# ROTA: /igrejas/criar  (POST)
# Cria uma nova igreja e um diretor para ela.
# Somente superadmin pode fazer isso.
# ============================================================
@app.route('/igrejas/criar', methods=['POST'])
@login_required
def criar_igreja():

    if not current_user.pode_gerenciar_igrejas():
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('index'))

    nome_igreja    = request.form['nome_igreja'].strip()
    nome_diretor   = request.form['nome_diretor'].strip()
    email_diretor  = request.form['email_diretor'].strip()
    senha_diretor  = request.form['senha_diretor'].strip()

    if not nome_igreja or not nome_diretor or not email_diretor or not senha_diretor:
        flash('Todos os campos são obrigatórios.', 'erro')
        return redirect(url_for('igrejas'))

    try:
        # Cria a igreja
        q(
            'INSERT INTO igrejas (nome, ativo, criado_em) VALUES (%s, %s, %s)',
            (nome_igreja, 1, date.today().strftime('%Y-%m-%d')),
            commit=True
        )

        # Busca o ID da igreja criada
        igreja = q(
            'SELECT id FROM igrejas WHERE nome = %s',
            (nome_igreja,),
            one=True
        )

        # Cria o diretor vinculado à igreja
        senha_hash = generate_password_hash(senha_diretor)
        q(
            '''INSERT INTO usuarios (nome, email, senha, perfil, igreja_id)
               VALUES (%s, %s, %s, %s, %s)''',
            (nome_diretor, email_diretor, senha_hash, 'diretor', igreja['id']),
            commit=True
        )

        flash(f'Igreja "{nome_igreja}" criada com sucesso!', 'sucesso')

    except Exception as e:
        get_db().rollback()
        flash('Erro ao criar igreja. Verifique se o email do diretor já existe.', 'erro')

    return redirect(url_for('igrejas'))


# ============================================================
# ROTA: /igrejas/<id>/deletar  (POST)
# Deleta uma igreja e todos os dados vinculados.
# Somente superadmin pode fazer isso.
# ============================================================
@app.route('/igrejas/<int:igreja_id>/deletar', methods=['POST'])
@login_required
def deletar_igreja(igreja_id):

    if not current_user.pode_gerenciar_igrejas():
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('igrejas'))

    q('DELETE FROM igrejas WHERE id = %s', (igreja_id,), commit=True)
    flash('Igreja removida.', 'sucesso')
    return redirect(url_for('igrejas'))

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

        # Email ou Senha Incorreta, retorna um erro
        if usuario is None or not check_password_hash(usuario['senha'], senha):
            flash('Email ou senha incorretos.', 'erro')
            return redirect(url_for('login'))
        
        # Busca as igrejas do usuário
        igrejas = q('''
            SELECT ui.*, i.nome AS igreja_nome
            FROM usuario_igrejas ui
            JOIN igrejas i ON i.id = ui.igreja_id
            WHERE ui.usuario_id = %s AND ui.ativo = 1
            ORDER BY i.nome
        ''', (usuario['id'],))

        # Tudo certo — cria o objeto Usuario e registra na sessão
        usuario_obj = Usuario(
            id     = usuario['id'],
            nome   = usuario['nome'],
            email  = usuario['email'],
            perfil = usuario['perfil'],
            igreja_atual = None,
            perfil_atual = None
        )
        login_user(usuario_obj)
        # A partir daqui, current_user terá os dados desse usuário

        # Superadmin entra direto
        if usuario['perfil'] == 'superadmin':
            session['igreja_atual'] = None
            return redirect(url_for('index'))
        
        # Usuário sem nenhuma igreja
        if not igrejas:
            flash('Você não está vinculado a nenhuma igreja.', 'erro')
            logout_user()
            return redirect(url_for('login'))
        
        # Usuário com apenas uma igreja — entra direto
        if len(igrejas) == 1:
            session['igreja_atual'] = igrejas[0]['igreja_id']
            return redirect(url_for('selecionar_igreja'))
        
        # Usuário com múltiplas igrejas — vai para tela de seleção
        return redirect(url_for('selecionar_igreja'))

    # Se for GET, apenas exibe o formulário
    return render_template('login.html')

# ============================================================
# ROTA: /selecionar-igreja  (GET e POST)
# Permite ao usuário escolher qual igreja acessar.
# ============================================================
@app.route('/selecionar-igreja', methods=['GET', 'POST'])
@login_required
def selecionar_igreja():

    if current_user.e_superadmin():
        return redirect(url_for('index'))

    # Busca as igrejas do usuário
    igrejas = q('''
        SELECT ui.*, i.nome AS igreja_nome
        FROM usuario_igrejas ui
        JOIN igrejas i ON i.id = ui.igreja_id
        WHERE ui.usuario_id = %s AND ui.ativo = 1
        ORDER BY i.nome
    ''', (current_user.id,))

    # Se só tem uma igreja seleciona automaticamente
    if len(igrejas) == 1:
        igreja_id = igrejas[0]['igreja_id']
        session['igreja_atual'] = igreja_id
        # Recarrega o usuário com o perfil correto
        usuario_atualizado = carregar_usuario(current_user.id, igreja_id)
        login_user(usuario_atualizado)
        return redirect(url_for('index'))

    if request.method == 'POST':
        igreja_id = int(request.form['igreja_id'])

        vinculo = q('''
            SELECT * FROM usuario_igrejas
            WHERE usuario_id = %s AND igreja_id = %s AND ativo = 1
        ''', (current_user.id, igreja_id), one=True)

        if not vinculo:
            flash('Você não tem acesso a essa igreja.', 'erro')
            return redirect(url_for('selecionar_igreja'))

        session['igreja_atual'] = igreja_id
        # Recarrega o usuário com o perfil correto
        usuario_atualizado = carregar_usuario(current_user.id, igreja_id)
        login_user(usuario_atualizado)
        return redirect(url_for('index'))

    return render_template('selecionar_igreja.html', igrejas=igrejas)

#----------------------------------------------------------------------------------------------
# Rota de minha Igrejas
#----------------------------------------------------------------------------------------------

@app.route('/minhas-igrejas')
@login_required
def minhas_igrejas():
    if current_user.e_superadmin():
        return redirect(url_for('index'))

    igrejas = q('''
        SELECT ui.*, i.nome AS igreja_nome
        FROM usuario_igrejas ui
        JOIN igrejas i ON i.id = ui.igreja_id
        WHERE ui.usuario_id = %s AND ui.ativo = 1
        ORDER BY i.nome
    ''', (current_user.id,))

    # Se só tem uma igreja não precisa trocar
    if len(igrejas) <= 1:
        flash('Você só tem acesso a uma igreja.', 'erro')
        return redirect(url_for('index'))

    return render_template('selecionar_igreja.html', igrejas=igrejas)


# ============================================================
# ROTA: /logout
# Encerra a sessão e redireciona para o login
# ============================================================
@app.route('/logout')
@login_required
# @login_required bloqueia a rota se não estiver logado
def logout():
    session.pop('igreja_atual', None)
    logout_user()
    return redirect(url_for('login'))


# ============================================================
# ROTA: /  (página principal)
# Protegida — só acessível com login
# ============================================================
@app.route('/')
@login_required
def index():
    # Usuário logado mas sem igreja selecionada
    if not current_user.e_superadmin() and not current_user.igreja_atual:
        return redirect(url_for('selecionar_igreja'))
    return render_template('index.html')
 
# ============================================================
# ROTA: /usuarios  (GET)
# Lista todos os usuários do sistema.
# Somente diretor e coordenador podem acessar.
# ============================================================
@app.route('/usuarios')
@login_required
def usuarios():

    if not current_user.pode_gerenciar_usuarios():
        flash('Você não tem permissão para acessar essa página.', 'erro')
        return redirect(url_for('index'))

    # Superadmin vê todos os usuários
    # Diretor e coordenador veem só os usuários da sua igreja
    if current_user.e_superadmin():
        # Superadmin vê todos os usuários com suas igrejas
        lista_usuarios = q('''
            SELECT u.*,
                   STRING_AGG(i.nome || ' (' || ui.perfil || ')', ', ') AS igrejas_info,
                   MAX(CASE WHEN u.perfil != 'superadmin' THEN ui.perfil END) AS perfil_igreja
            FROM usuarios u
            LEFT JOIN usuario_igrejas ui ON ui.usuario_id = u.id AND ui.ativo = 1
            LEFT JOIN igrejas i ON i.id = ui.igreja_id
            GROUP BY u.id
            ORDER BY u.nome
        ''')
    else:
        # Diretor/coordenador vê usuários da sua igreja
        lista_usuarios = q('''
            SELECT u.*, ui.perfil AS perfil_igreja
            FROM usuarios u
            JOIN usuario_igrejas ui ON ui.usuario_id = u.id
            WHERE ui.igreja_id = %s AND ui.ativo = 1
            ORDER BY u.nome
        ''', (current_user.igreja_atual,))

    # Lista de igrejas para o superadmin vincular usuários
    todas_igrejas = q('SELECT * FROM igrejas ORDER BY nome') \
                    if current_user.e_superadmin() else []

    return render_template(
        'usuarios.html',
        usuarios      = lista_usuarios,
        todas_igrejas = todas_igrejas
    )


# ============================================================
# ROTA: /usuarios/criar  (POST)
# Cria um novo usuário.
# Somente diretor e coordenador podem criar.
# ============================================================
@app.route('/usuarios/criar', methods=['POST'])
@login_required
def criar_usuario():

    if current_user.perfil not in ['superadmin', 'diretor', 'coordenador']:
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('index'))

    nome       = request.form['nome'].strip()
    email      = request.form['email'].strip()
    senha      = request.form['senha'].strip()
    perfil     = request.form['perfil']
    igreja_id = request.form.get('igreja_id')

    if not nome or not email or not senha or not perfil:
        flash('Todos os campos são obrigatórios.', 'erro')
        return redirect(url_for('usuarios'))

    # Perfis válidos
    if perfil not in ['diretor', 'coordenador', 'secretaria', 'professor']:
        flash('Perfil inválido.', 'erro')
        return redirect(url_for('usuarios'))

    # Diretor e coordenador criam usuários vinculados à sua igreja
    # Superadmin define a igreja
    if current_user.e_superadmin():
        if not igreja_id:
            flash('Selecione uma igreja.', 'erro')
            return redirect(url_for('usuarios'))
    else:
        igreja_id = current_user.igreja_atual

    senha_hash = generate_password_hash(senha)

    try:
        # Verifica se o usuário já existe
        usuario_existente = q(
            'SELECT id FROM usuarios WHERE email = %s',
            (email,),
            one=True
        )

        if usuario_existente:
            usuario_id = usuario_existente['id']
        else:
            # Cria o usuário novo
            q(
                '''INSERT INTO usuarios (nome, email, senha, perfil)
                   VALUES (%s, %s, %s, %s)''',
                (nome, email, senha_hash, 'usuario'),
                commit=True
            )
            usuario_id = q(
                'SELECT id FROM usuarios WHERE email = %s',
                (email,),
                one=True
            )['id']

        # Verifica se já tem vínculo com essa igreja
        vinculo = q('''
            SELECT id FROM usuario_igrejas
            WHERE usuario_id = %s AND igreja_id = %s
        ''', (usuario_id, igreja_id), one=True)

        if vinculo:
            # Atualiza o perfil se já existir
            q('''
                UPDATE usuario_igrejas
                SET perfil = %s, ativo = 1
                WHERE usuario_id = %s AND igreja_id = %s
            ''', (perfil, usuario_id, igreja_id), commit=True)
            flash(f'Vínculo de "{nome}" atualizado!', 'sucesso')
        else:
            # Cria o vínculo
            q('''
                INSERT INTO usuario_igrejas (usuario_id, igreja_id, perfil)
                VALUES (%s, %s, %s)
            ''', (usuario_id, int(igreja_id), perfil), commit=True)
            flash(f'Usuário "{nome}" criado com sucesso!', 'sucesso')

    except Exception as e:
        get_db().rollback()
        flash(f'Erro ao criar usuário: {str(e)}', 'erro')

    return redirect(url_for('usuarios'))


# ============================================================
# ROTA: /usuarios/<id>/deletar  (POST)
# Deleta um usuário.
# Não é possível deletar a si mesmo.
# ============================================================
@app.route('/usuarios/<int:usuario_id>/deletar', methods=['POST'])
@login_required
def deletar_usuario(usuario_id):

    if not current_user.pode_gerenciar_usuarios():
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('usuarios'))

    # Impede que o usuário delete a si mesmo
    if usuario_id == current_user.id:
        flash('Você não pode deletar sua própria conta.', 'erro')
        return redirect(url_for('usuarios'))
    
    if current_user.e_superadmin():
        # Superadmin deleta o usuário completamente
        q('DELETE FROM usuarios WHERE id = %s', (usuario_id,), commit=True)
    else:
        # Diretor/coordenador apenas remove o vínculo com a igreja
        q('''
            DELETE FROM usuario_igrejas
            WHERE usuario_id = %s AND igreja_id = %s
        ''', (usuario_id, current_user.igreja_atual), commit=True)

    flash('Usuário removido.', 'sucesso')
    return redirect(url_for('usuarios'))

# ============================================================
# ROTA: /usuarios/vincular  (POST)
# Vincula um usuário já existente a uma igreja com um perfil.
# ============================================================
@app.route('/usuarios/vincular', methods=['POST'])
@login_required
def vincular_usuario():

    if not current_user.pode_gerenciar_usuarios():
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('usuarios'))

    email     = request.form['email'].strip()
    perfil    = request.form['perfil_vincular']
    igreja_id = request.form.get('igreja_id_vincular')

    if not email or not perfil:
        flash('Email e perfil são obrigatórios.', 'erro')
        return redirect(url_for('usuarios'))

    if current_user.e_superadmin():
        if not igreja_id:
            flash('Selecione uma igreja.', 'erro')
            return redirect(url_for('usuarios'))
    else:
        igreja_id = current_user.igreja_atual

    # Busca o usuário pelo email
    usuario = q(
        'SELECT * FROM usuarios WHERE email = %s',
        (email,),
        one=True
    )

    if not usuario:
        flash('Nenhum usuário encontrado com esse email.', 'erro')
        return redirect(url_for('usuarios'))

    # Verifica se já tem vínculo com essa igreja
    vinculo = q('''
        SELECT id FROM usuario_igrejas
        WHERE usuario_id = %s AND igreja_id = %s
    ''', (usuario['id'], igreja_id), one=True)

    if vinculo:
        # Atualiza o perfil
        q('''
            UPDATE usuario_igrejas
            SET perfil = %s, ativo = 1
            WHERE usuario_id = %s AND igreja_id = %s
        ''', (perfil, usuario['id'], igreja_id), commit=True)
        flash(f'Perfil de "{usuario["nome"]}" atualizado!', 'sucesso')
    else:
        # Cria o vínculo
        q('''
            INSERT INTO usuario_igrejas (usuario_id, igreja_id, perfil)
            VALUES (%s, %s, %s)
        ''', (usuario['id'], int(igreja_id), perfil), commit=True)
        flash(f'"{usuario["nome"]}" vinculado com sucesso!', 'sucesso')

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
# ROTA: /turmas/<id>/professores  (GET)
# Mostra os professores designados para uma turma
# e permite adicionar/remover.
# ============================================================
@app.route('/turmas/<int:turma_id>/professores')
@login_required
def professores_turma(turma_id):

    if not current_user.pode_gerenciar_alunos():
        flash('Você não tem permissão para acessar essa página.', 'erro')
        return redirect(url_for('turmas'))

    turma = q('SELECT * FROM turmas WHERE id = %s', (turma_id,), one=True)

    if turma is None:
        flash('Turma não encontrada.', 'erro')
        return redirect(url_for('turmas'))

    # Verifica se a turma pertence à igreja do usuário
    if not current_user.e_superadmin() and turma['igreja_id'] != current_user.igreja_id:
        flash('Você não tem acesso a essa turma.', 'erro')
        return redirect(url_for('turmas'))

    # Professores já designados para essa turma
    professores_designados = q('''
        SELECT u.id, u.nome, u.email, pt.id AS vinculo_id, pt.ativo
        FROM professor_turmas pt
        JOIN usuarios u ON u.id = pt.professor_id
        WHERE pt.turma_id = %s
        ORDER BY u.nome
    ''', (turma_id,))

    # Professores disponíveis da mesma igreja para adicionar
    if current_user.e_superadmin():
        professores_disponiveis = q('''
            SELECT * FROM usuarios
            WHERE perfil = 'professor'
            AND id NOT IN (
                SELECT professor_id FROM professor_turmas WHERE turma_id = %s
            )
            ORDER BY nome
        ''', (turma_id,))
    else:
        professores_disponiveis = q('''
            SELECT * FROM usuarios
            WHERE perfil = 'professor'
            AND igreja_id = %s
            AND id NOT IN (
                SELECT professor_id FROM professor_turmas WHERE turma_id = %s
            )
            ORDER BY nome
        ''', (current_user.igreja_id, turma_id))

    return render_template(
        'professores_turma.html',
        turma                  = turma,
        professores_designados = professores_designados,
        professores_disponiveis= professores_disponiveis
    )


# ============================================================
# ROTA: /turmas/<id>/professores/adicionar  (POST)
# Designa um professor para uma turma.
# ============================================================
@app.route('/turmas/<int:turma_id>/professores/adicionar', methods=['POST'])
@login_required
def adicionar_professor_turma(turma_id):

    if not current_user.pode_gerenciar_alunos():
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('professores_turma', turma_id=turma_id))

    professor_id = request.form['professor_id']

    # Verifica se já existe o vínculo
    vinculo = q('''
        SELECT id FROM professor_turmas
        WHERE professor_id = %s AND turma_id = %s
    ''', (professor_id, turma_id), one=True)

    if vinculo:
        # Reativa o vínculo se estava inativo
        q('''
            UPDATE professor_turmas SET ativo = 1
            WHERE professor_id = %s AND turma_id = %s
        ''', (professor_id, turma_id), commit=True)
    else:
        q('''
            INSERT INTO professor_turmas (professor_id, turma_id, ativo)
            VALUES (%s, %s, 1)
        ''', (professor_id, turma_id), commit=True)

    flash('Professor designado com sucesso!', 'sucesso')
    return redirect(url_for('professores_turma', turma_id=turma_id))


# ============================================================
# ROTA: /turmas/professores/<vinculo_id>/remover  (POST)
# Remove o acesso de um professor a uma turma.
# ============================================================
@app.route('/turmas/professores/<int:vinculo_id>/remover', methods=['POST'])
@login_required
def remover_professor_turma(vinculo_id):

    if not current_user.pode_gerenciar_alunos():
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('turmas'))

    # Busca o vínculo para saber qual turma redirecionar
    vinculo = q(
        'SELECT * FROM professor_turmas WHERE id = %s',
        (vinculo_id,),
        one=True
    )

    q('DELETE FROM professor_turmas WHERE id = %s', (vinculo_id,), commit=True)
    flash('Professor removido da turma.', 'sucesso')
    return redirect(url_for('professores_turma', turma_id=vinculo['turma_id'])) 
    
# ============================================================
# ROTA: /turmas  (GET)
# Lista turmas filtradas por igreja/professor
# ============================================================
@app.route('/turmas')
@login_required
def turmas():

    # Superadmin vê todas as turmas
    if current_user.e_superadmin():
        todas_turmas = q('SELECT t.*, i.nome AS igreja_nome FROM turmas t LEFT JOIN igrejas i ON i.id = t.igreja_id ORDER BY t.nome')
        todas_igrejas = q('SELECT * FROM igrejas ORDER BY nome') if current_user.e_superadmin() else []

    # Professor vê só as turmas que foi designado
    elif current_user.e_professor():
        todas_turmas = q('''
            SELECT t.*, i.nome AS igreja_nome
            FROM turmas t
            LEFT JOIN igrejas i ON i.id = t.igreja_id
            JOIN professor_turmas pt ON pt.turma_id = t.id
            WHERE pt.professor_id = %s AND pt.ativo = 1
            ORDER BY t.nome
        ''', (current_user.id,))

    # Diretor, coordenador e secretaria veem só turmas da sua igreja
    else:
        todas_turmas = q('''
            SELECT t.*, i.nome AS igreja_nome
            FROM turmas t
            LEFT JOIN igrejas i ON i.id = t.igreja_id
            WHERE t.igreja_id = %s
            ORDER BY t.nome
        ''', (current_user.igreja_id,))
    
     # Busca igrejas para o superadmin selecionar no modal
    todas_igrejas = q('SELECT * FROM igrejas ORDER BY nome') if current_user.e_superadmin() else []

    return render_template('turmas.html', turmas=todas_turmas, todas_igrejas=todas_igrejas)

# ============================================================
# ROTA: /turmas/criar  (POST)
# ============================================================
@app.route('/turmas/criar', methods=['POST'])
@login_required
def criar_turma():

    if not current_user.pode_gerenciar_alunos():
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('turmas'))

    nome = request.form['nome'].strip()

    if not nome:
        flash('O nome da turma não pode ser vazio.', 'erro')
        return redirect(url_for('turmas'))

    # Superadmin precisa selecionar a igreja
    # Outros usuários criam na sua própria igreja
    if current_user.e_superadmin():
        igreja_id = request.form.get('igreja_id')
        if not igreja_id:
            flash('Selecione uma igreja para a turma.', 'erro')
            return redirect(url_for('turmas'))
    else:
        igreja_id = current_user.igreja_id

    try:
        q(
            'INSERT INTO turmas (nome, igreja_id) VALUES (%s, %s)',
            (nome, igreja_id),
            commit=True
        )
        flash(f'Turma "{nome}" criada com sucesso!', 'sucesso')
    except:
        get_db().rollback()
        flash('Já existe uma turma com esse nome.', 'erro')

    return redirect(url_for('turmas'))



# ============================================================
# ROTA: /turmas/<id>/deletar  (POST)
# ============================================================
@app.route('/turmas/<int:turma_id>/deletar', methods=['POST'])
@login_required
def deletar_turma(turma_id):

    if not current_user.pode_gerenciar_alunos():
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('turmas'))

    # Verifica se a turma pertence à igreja do usuário
    turma = q('SELECT * FROM turmas WHERE id = %s', (turma_id,), one=True)

    if not current_user.e_superadmin() and turma['igreja_id'] != current_user.igreja_id:
        flash('Você não tem permissão para deletar essa turma.', 'erro')
        return redirect(url_for('turmas'))

    q('DELETE FROM turmas WHERE id = %s', (turma_id,), commit=True)
    flash('Turma removida.', 'sucesso')
    return redirect(url_for('turmas'))


# ============================================================
# ROTA: /turmas/<id>/alunos  (GET)
# ============================================================
@app.route('/turmas/<int:turma_id>/alunos')
@login_required
def alunos(turma_id):

    turma = q('SELECT * FROM turmas WHERE id = %s', (turma_id,), one=True)

    if turma is None:
        flash('Turma não encontrada.', 'erro')
        return redirect(url_for('turmas'))

    # Verifica se o usuário tem acesso a essa turma
    if not current_user.e_superadmin():
        if current_user.e_professor():
            acesso = q('''
                SELECT id FROM professor_turmas
                WHERE professor_id = %s AND turma_id = %s AND ativo = 1
            ''', (current_user.id, turma_id), one=True)
            if not acesso:
                flash('Você não tem acesso a essa turma.', 'erro')
                return redirect(url_for('turmas'))
        elif turma['igreja_id'] != current_user.igreja_id:
            flash('Você não tem acesso a essa turma.', 'erro')
            return redirect(url_for('turmas'))

    lista_alunos = q(
        'SELECT * FROM alunos WHERE turma_id = %s ORDER BY nome',
        (turma_id,)
    )

    return render_template('alunos.html', turma=turma, alunos=lista_alunos)

# ============================================================
# ROTA: /turmas/<id>/alunos/adicionar  (POST)
# ============================================================
@app.route('/turmas/<int:turma_id>/alunos/adicionar', methods=['POST'])
@login_required
def adicionar_aluno(turma_id):

    if not current_user.pode_gerenciar_alunos():
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('alunos', turma_id=turma_id))

    turma = q('SELECT * FROM turmas WHERE id = %s', (turma_id,), one=True)

    if not current_user.e_superadmin() and turma['igreja_id'] != current_user.igreja_id:
        flash('Você não tem acesso a essa turma.', 'erro')
        return redirect(url_for('turmas'))

    nome = request.form['nome'].strip()
    celula = request.form.get('celula', '').strip()

    if not nome:
        flash('O nome do aluno não pode ser vazio.', 'erro')
        return redirect(url_for('alunos', turma_id=turma_id))

    q(
        'INSERT INTO alunos (nome, turma_id, celula) VALUES (%s, %s, %s)',
        (nome, turma_id, celula or None),
        commit=True
    )
    flash(f'Aluno "{nome}" adicionado!', 'sucesso')
    return redirect(url_for('alunos', turma_id=turma_id))


# ============================================================
# ROTA: /alunos/<id>/deletar  (POST)
# ============================================================
@app.route('/alunos/<int:aluno_id>/deletar', methods=['POST'])
@login_required
def deletar_aluno(aluno_id):

    aluno = q('SELECT * FROM alunos WHERE id = %s', (aluno_id,), one=True)
    turma = q('SELECT * FROM turmas WHERE id = %s', (aluno['turma_id'],), one=True)

    if not current_user.pode_gerenciar_alunos():
        flash('Você não tem permissão para fazer isso.', 'erro')
        return redirect(url_for('alunos', turma_id=aluno['turma_id']))

    if not current_user.e_superadmin() and turma['igreja_id'] != current_user.igreja_id:
        flash('Você não tem acesso a essa turma.', 'erro')
        return redirect(url_for('turmas'))

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
    

# --- INICIALIZAÇÃO ---

init_db()
if __name__ == '__main__':
    
    app.run(debug=False)