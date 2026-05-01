# ============================================================
# auth.py
# Responsável por:
# - Definir o que é um "usuário" para o Flask-Login
# - Carregar o usuário do banco a partir do ID guardado na sessão
# ============================================================

from flask_login import UserMixin
# UserMixin é uma classe do Flask-Login que já implementa
# 4 métodos obrigatórios para o sistema de login funcionar:
#   - is_authenticated → o usuário está logado?
#   - is_active        → a conta está ativa?
#   - is_anonymous     → é um visitante sem login?
#   - get_id()         → retorna o ID do usuário como string
# Herdando ela, não precisamos implementar esses métodos na mão.

from database import q
# Importamos nossa função auxiliar de queries


# ============================================================
# CLASSE: Usuario
# Representa o usuário logado no sistema.
# O Flask-Login vai usar essa classe para saber quem está logado.
# ============================================================
class Usuario(UserMixin):

    def __init__(self, id, nome, email, perfil, igreja_atual=None, perfil_atual=None):
        # __init__ é o construtor — roda quando criamos um Usuario
        # Guardamos as informações do usuário como atributos do objeto
        self.id     = id
        self.nome   = nome
        self.email  = email
        self.perfil = perfil
        self.igreja_atual = igreja_atual
        self.perfil_atual = perfil_atual
        # igreja_id None = superadmin
        # perfil pode ser: 'diretor', 'coordenador', 'secretaria', 'professor'

    def pode_gerenciar_alunos(self):
        """
        Retorna True se o usuário tem permissão para
        adicionar ou remover alunos e turmas.
        Somente diretor, coordenador e secretaria podem fazer isso.
        """
        if self.e_superadmin():
            return True
        return self.perfil_atual in ['diretor', 'coordenador', 'secretaria']
    
    def pode_gerenciar_usuarios(self):
        """
        Retorna True se pode criar e remover usuários.
        - Superadmin gerencia usuários de qualquer igreja
        - Diretor e coordenador gerenciam usuários da sua própria igreja
        """
        if self.e_superadmin():
            return True
        return self.perfil_atual in ['diretor', 'coordenador']
        
    def pode_gerenciar_igrejas(self):
        """
        Retorna True se pode criar e gerenciar igrejas.
        Somente o superadmin pode fazer isso.
        """
        return self.e_superadmin()

    def e_professor(self):
        """
        Retorna True se o usuário é professor.
        Professores podem fazer chamada e lançar questionários.
        """
        return self.perfil_atual == 'professor'
    
    def e_superadmin(self):
        return self.perfil == 'superadmin'
    
    def get_igreja_id(self):
        """
        Retorna o ID da igreja atual do usuário.
        Superadmin não tem igreja fixa.
        """
        return self.igreja_atual


# ============================================================
# FUNÇÃO: carregar_usuario(user_id)
# O Flask-Login chama essa função automaticamente em toda
# requisição para saber quem está logado.
# Ele pega o ID guardado na sessão e busca o usuário no banco.
# ============================================================
def carregar_usuario(user_id, igreja_id=None):
    """
    Busca o usuário no banco pelo ID.
    Se igreja_id for passado, carrega também o perfil naquela igreja.
    """
    usuario = q(
        'SELECT * FROM usuarios WHERE id = %s',
        (user_id,),
        one=True
    )

    if usuario is None:
        # ID não encontrado no banco — retorna None
        # O Flask-Login vai tratar isso como "não logado"
        return None
    
    perfil_atual = None
    igreja_atual = None

    if igreja_id:
        # Busca o perfil do usuário na igreja selecionada
        vinculo = q(
            '''SELECT perfil FROM usuario_igrejas
               WHERE usuario_id = %s AND igreja_id = %s AND ativo = 1''',
            (user_id, igreja_id),
            one=True
        )
        if vinculo:
            perfil_atual = vinculo['perfil']
            igreja_atual = igreja_id

    elif usuario['perfil'] == 'superadmin':
        perfil_atual = 'superadmin'
        
    # Cria e retorna um objeto Usuario com os dados do banco
    return Usuario(
        id        = usuario['id'],
        nome      = usuario['nome'],
        email     = usuario['email'],
        perfil            = usuario['perfil'],
        igreja_atual = igreja_atual,
        perfil_atual = perfil_atual
    )