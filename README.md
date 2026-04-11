# 📋 Chamada Escolar — Escola de Líderes

Sistema web para controle de chamadas, frequência e entrega de questionários escolares.

---

## 📌 Funcionalidades

- **Login com perfis** — cada usuário tem permissões diferentes
- **Gerenciamento de usuários** — diretor e coordenador criam e removem usuários
- **Controle de acesso por perfil**
  - Diretor e Coordenador → gerenciam turmas, alunos e usuários
  - Secretaria → gerencia turmas e alunos
  - Professor → faz chamadas e lança questionários
- **Chamada diária** — professor marca presença e falta de cada aluno
- **Histórico de chamadas** — frequência por aluno com alerta abaixo de 75%
- **Questionários** — professor registra entregas de vários alunos de uma vez
- **Exportar CSV** — histórico de chamadas e questionários compatível com Excel
- **Responsivo** — funciona bem em celular e desktop

---

## 🛠️ Tecnologias utilizadas

| Tecnologia | Uso |
|---|---|
| Python 3 | Linguagem principal |
| Flask | Framework web |
| Flask-Login | Autenticação e sessão |
| PostgreSQL | Banco de dados |
| psycopg2 | Conexão Python com PostgreSQL |
| Werkzeug | Hash de senhas |
| python-dotenv | Variáveis de ambiente |
| Tailwind CSS | Estilização do frontend |

---

## 📁 Estrutura do projeto
chamada-escolar/
├── app.py              # Rotas e lógica principal
├── auth.py             # Classe de usuário e autenticação
├── database.py         # Conexão e queries do banco
├── requirements.txt    # Dependências do projeto
├── Procfile            # Configuração para deploy
├── .env                # Variáveis de ambiente
├── .gitignore          # Arquivos ignorados pelo Git
└── templates/
├── base.html               # Template base com navbar
├── login.html              # Tela de login
├── index.html              # Página inicial
├── turmas.html             # Lista de turmas
├── alunos.html             # Lista de alunos da turma
├── chamada.html            # Fazer chamada
├── historico.html          # Histórico de chamadas
├── questionarios.html      # Lançar questionários
├── questionarios_aluno.html # Histórico do aluno
└── usuarios.html           # Gerenciar usuários

---

## ⚙️ Como rodar localmente

### 1. Clone o repositório
```bash
git clone https://github.com/Lucasbatistasousa/chamada-app.git
cd chamada-app
```

### 2. Crie o ambiente virtual
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```

### 4. Configure o `.env`
Crie um arquivo `.env` na raiz do projeto:
DATABASE_URL=postgresql://usuario:senha@localhost:5432/nome_do_banco
SECRET_KEY=sua_chave_secreta_aqui

Para gerar a SECRET_KEY:
```bash
python -c "import os; print(os.urandom(24).hex())"
```

### 5. Rode o projeto
```bash
python app.py
```

Acesse: **http://localhost:5000**

### 6. Crie o primeiro usuário administrador
Acesse no navegador:
http://localhost:5000/criar-admin

Isso cria um usuário com perfil `diretor`:
- **Email:** admin@escola.com
- **Senha:** admin123

> ⚠️ Troque a senha após o primeiro login e apague a rota `/criar-admin` do `app.py` antes de colocar o projeto no ar!

---

## 👤 Perfis de usuário

| Perfil | Turmas e Alunos | Chamada | Questionários | Usuários |
|---|---|---|---|---|
| Diretor | ✅ | ✅ | ✅ | ✅ |
| Coordenador | ✅ | ✅ | ✅ | ✅ |
| Secretaria | ✅ | ✅ | ✅ | ❌ |
| Professor | ❌ | ✅ | ✅ | ❌ |

---

## 🚀 Deploy no Render

### 1. Gere o `requirements.txt`
```bash
pip freeze > requirements.txt
```

### 2. Crie o `Procfile` na raiz do projeto
web: gunicorn app:app

### 3. Crie o `.gitignore`
venv/
.env
pycache/
*.pyc
*.pyo
*.db
.DS_Store
Thumbs.db

### 4. Suba o código no GitHub
```bash
git init
git add .
git commit -m "primeiro commit"
git remote add origin https://github.com/Lucasbatistasousa/chamada-app.git
git push -u origin main
```

### 5. Configure no Render
1. Acesse [render.com](https://render.com) e crie uma conta
2. Crie um banco **PostgreSQL** → copie a **Internal Database URL**
3. Crie um **Web Service** conectado ao seu repositório
4. Configure:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
5. Em **Environment**, adicione as variáveis:
   - `DATABASE_URL` → cole a Internal Database URL do banco
   - `SECRET_KEY` → gere com `python -c "import os; print(os.urandom(24).hex())"`
6. Clique em **Deploy**

> ⚠️ Após o deploy, acesse `/criar-admin` para criar o primeiro usuário e depois apague essa rota do código.

---

## 🔒 Segurança

- Senhas armazenadas como **hash** via Werkzeug — nunca em texto puro
- Variáveis sensíveis fora do código no `.env`
- Proteção contra **SQL Injection** via parâmetros `%s` no psycopg2
- Controle de acesso por perfil em todas as rotas sensíveis
- Usuário não consegue deletar a própria conta

---

## 📄 Licença

Este projeto está sob a licença MIT.

Crie o .gitignore
venv/
.env
__pycache__/
*.pyc
*.pyo
*.db
.DS_Store
Thumbs.db

Gere o requirements.txt
bashpip freeze > requirements.txt