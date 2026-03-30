# 📋 Chamada Digital

App de chamada escolar feito em Python + Flask.

## Funcionalidades

- ✅ Múltiplas turmas
- ✅ Cadastro de alunos por turma
- ✅ Fazer chamada com clique (Presente / Falta)
- ✅ Histórico de chamadas com estatísticas
- ✅ Exportar para CSV (compatível com Excel)

---

## Rodar localmente

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Iniciar o servidor
python app.py
```

Acesse: http://localhost:5000

---

## Deploy online (Render.com — gratuito)

1. Crie uma conta em https://render.com
2. Clique em **New > Web Service**
3. Conecte seu repositório GitHub com este projeto
4. Configure:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
   - **Environment:** Python 3
5. Clique em **Deploy**

> ⚠️ O Render gratuito usa disco efêmero — o banco SQLite pode ser apagado ao reiniciar.
> Para produção com persistência, use o **Render Disk** (pago) ou migre para PostgreSQL.

---

## Deploy no Railway (alternativa)

1. Acesse https://railway.app
2. Clique em **New Project > Deploy from GitHub**
3. Selecione o repositório
4. Railway detecta automaticamente o `Procfile` e faz o deploy

---

## Estrutura

```
chamada-app/
├── app.py           # Rotas Flask
├── database.py      # SQLite
├── requirements.txt
├── Procfile         # Para deploy
└── templates/
    ├── base.html
    ├── index.html   # Lista de turmas
    ├── chamada.html # Fazer chamada
    └── historico.html
```
