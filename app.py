from flask import Flask, render_template, request, jsonify, send_file
from database import init_db, get_db
import io
import csv
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    db = get_db()
    turmas = db.execute('SELECT * FROM turmas ORDER BY nome').fetchall()
    return render_template('index.html', turmas=turmas)

# ── TURMAS ──────────────────────────────────────────────────────────────────

@app.route('/turmas', methods=['POST'])
def criar_turma():
    data = request.json
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({'erro': 'Nome obrigatório'}), 400
    db = get_db()
    try:
        db.execute('INSERT INTO turmas (nome) VALUES (?)', (nome,))
        db.commit()
        turma = db.execute('SELECT * FROM turmas WHERE nome = ?', (nome,)).fetchone()
        return jsonify({'id': turma['id'], 'nome': turma['nome']})
    except:
        return jsonify({'erro': 'Turma já existe'}), 400

@app.route('/turmas/<int:turma_id>', methods=['DELETE'])
def deletar_turma(turma_id):
    db = get_db()
    db.execute('DELETE FROM turmas WHERE id = ?', (turma_id,))
    db.commit()
    return jsonify({'ok': True})

# ── ALUNOS ───────────────────────────────────────────────────────────────────

@app.route('/turmas/<int:turma_id>/alunos')
def listar_alunos(turma_id):
    db = get_db()
    alunos = db.execute(
        'SELECT * FROM alunos WHERE turma_id = ? ORDER BY nome', (turma_id,)
    ).fetchall()
    return jsonify([dict(a) for a in alunos])

@app.route('/alunos', methods=['POST'])
def criar_aluno():
    data = request.json
    nome = data.get('nome', '').strip()
    turma_id = data.get('turma_id')
    if not nome or not turma_id:
        return jsonify({'erro': 'Nome e turma obrigatórios'}), 400
    db = get_db()
    db.execute('INSERT INTO alunos (nome, turma_id) VALUES (?, ?)', (nome, turma_id))
    db.commit()
    aluno = db.execute('SELECT * FROM alunos WHERE nome = ? AND turma_id = ?', (nome, turma_id)).fetchone()
    return jsonify(dict(aluno))

@app.route('/alunos/<int:aluno_id>', methods=['DELETE'])
def deletar_aluno(aluno_id):
    db = get_db()
    db.execute('DELETE FROM alunos WHERE id = ?', (aluno_id,))
    db.commit()
    return jsonify({'ok': True})

# ── CHAMADAS ──────────────────────────────────────────────────────────────────

@app.route('/chamada/<int:turma_id>')
def tela_chamada(turma_id):
    db = get_db()
    turma = db.execute('SELECT * FROM turmas WHERE id = ?', (turma_id,)).fetchone()
    if not turma:
        return 'Turma não encontrada', 404
    alunos = db.execute(
        'SELECT * FROM alunos WHERE turma_id = ? ORDER BY nome', (turma_id,)
    ).fetchall()
    return render_template('chamada.html', turma=turma, alunos=alunos)

@app.route('/chamada/salvar', methods=['POST'])
def salvar_chamada():
    data = request.json
    turma_id = data.get('turma_id')
    data_chamada = data.get('data') or datetime.now().strftime('%Y-%m-%d')
    presencas = data.get('presencas', {})  # {aluno_id: True/False}

    db = get_db()
    # Remove chamada anterior do mesmo dia/turma se existir
    chamada_existente = db.execute(
        'SELECT id FROM chamadas WHERE turma_id = ? AND data = ?', (turma_id, data_chamada)
    ).fetchone()
    if chamada_existente:
        db.execute('DELETE FROM presencas WHERE chamada_id = ?', (chamada_existente['id'],))
        db.execute('DELETE FROM chamadas WHERE id = ?', (chamada_existente['id'],))

    db.execute('INSERT INTO chamadas (turma_id, data) VALUES (?, ?)', (turma_id, data_chamada))
    chamada = db.execute(
        'SELECT id FROM chamadas WHERE turma_id = ? AND data = ?', (turma_id, data_chamada)
    ).fetchone()
    chamada_id = chamada['id']

    for aluno_id, presente in presencas.items():
        db.execute(
            'INSERT INTO presencas (chamada_id, aluno_id, presente) VALUES (?, ?, ?)',
            (chamada_id, int(aluno_id), 1 if presente else 0)
        )
    db.commit()
    return jsonify({'ok': True, 'chamada_id': chamada_id})

# ── HISTÓRICO ─────────────────────────────────────────────────────────────────

@app.route('/historico')
def historico():
    db = get_db()
    turmas = db.execute('SELECT * FROM turmas ORDER BY nome').fetchall()
    return render_template('historico.html', turmas=turmas)

@app.route('/historico/<int:turma_id>')
def historico_turma(turma_id):
    db = get_db()
    turma = db.execute('SELECT * FROM turmas WHERE id = ?', (turma_id,)).fetchone()
    chamadas = db.execute(
        'SELECT * FROM chamadas WHERE turma_id = ? ORDER BY data DESC', (turma_id,)
    ).fetchall()

    resultado = []
    for c in chamadas:
        presencas = db.execute('''
            SELECT a.nome, p.presente
            FROM presencas p
            JOIN alunos a ON a.id = p.aluno_id
            WHERE p.chamada_id = ?
            ORDER BY a.nome
        ''', (c['id'],)).fetchall()
        resultado.append({
            'id': c['id'],
            'data': c['data'],
            'presencas': [dict(p) for p in presencas],
            'total': len(presencas),
            'presentes': sum(1 for p in presencas if p['presente'])
        })

    return jsonify({'turma': dict(turma), 'chamadas': resultado})

# ── EXPORTAR CSV ──────────────────────────────────────────────────────────────

@app.route('/exportar/<int:turma_id>')
def exportar_csv(turma_id):
    db = get_db()
    turma = db.execute('SELECT * FROM turmas WHERE id = ?', (turma_id,)).fetchone()
    chamadas = db.execute(
        'SELECT * FROM chamadas WHERE turma_id = ? ORDER BY data', (turma_id,)
    ).fetchall()
    alunos = db.execute(
        'SELECT * FROM alunos WHERE turma_id = ? ORDER BY nome', (turma_id,)
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)

    # Cabeçalho
    header = ['Aluno'] + [c['data'] for c in chamadas] + ['Total Presenças', '% Presença']
    writer.writerow(header)

    for aluno in alunos:
        row = [aluno['nome']]
        total = 0
        for chamada in chamadas:
            p = db.execute(
                'SELECT presente FROM presencas WHERE chamada_id = ? AND aluno_id = ?',
                (chamada['id'], aluno['id'])
            ).fetchone()
            val = p['presente'] if p else None
            if val is None:
                row.append('-')
            elif val:
                row.append('P')
                total += 1
            else:
                row.append('F')
        pct = f"{round(total/len(chamadas)*100)}%" if chamadas else '-'
        row += [total, pct]
        writer.writerow(row)

    output.seek(0)
    return send_file(
        io.BytesIO(output.read().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'chamada_{turma["nome"]}_{datetime.now().strftime("%Y%m%d")}.csv'
    )

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
