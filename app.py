import os
from flask import Flask, render_template, request, url_for, redirect, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import datetime, date, timedelta
from functools import wraps

load_dotenv()

# --- 1. CONFIGURAÇÃO ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key-for-dev')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///escala.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- 2. MODELOS DO BANCO DE DADOS ---
usuario_habilidades = db.Table('usuario_habilidades',
    db.Column('usuario_id', db.Integer, db.ForeignKey('usuario.id'), primary_key=True),
    db.Column('habilidade_id', db.Integer, db.ForeignKey('habilidade.id'), primary_key=True)
)

class Habilidade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    funcao = db.Column(db.String(100), unique=True, nullable=False)

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    habilidades = db.relationship('Habilidade', secondary=usuario_habilidades, lazy='subquery',
                                  backref=db.backref('usuarios', lazy=True))
    def set_password(self, password): self.senha_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.senha_hash, password)

class Missa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    horario = db.Column(db.Time, nullable=False)
    vagas = db.relationship('Vaga', backref='missa', lazy=True, cascade="all, delete-orphan")
    arquivada = db.Column(db.Boolean, default=False, nullable=False) # Coluna para arquivamento

class Vaga(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    funcao = db.Column(db.String(100), nullable=False)
    missa_id = db.Column(db.Integer, db.ForeignKey('missa.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    usuario = db.relationship('Usuario')

# --- 3. LÓGICA DE LIMPEZA AUTOMÁTICA ---
@app.before_request
def cleanup_old_masses():
    cutoff_date = date.today() - timedelta(days=15)
    # Encontra missas com mais de 15 dias que ainda não foram arquivadas
    missas_para_arquivar = Missa.query.filter(Missa.data < cutoff_date, Missa.arquivada == False).all()
    if missas_para_arquivar:
        for missa in missas_para_arquivar:
            missa.arquivada = True
        db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash("Você não tem permissão para acessar esta página.", "warning")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- 4. ROTAS DE AUTENTICAÇÃO E PÁGINAS PRINCIPAIS ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        user = Usuario.query.filter_by(email=request.form.get('email')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Email ou senha inválidos.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

# --- 5. ROTAS DO PAINEL DO COORDENADOR ---
@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    missas = Missa.query.filter_by(arquivada=False).order_by(Missa.data.desc(), Missa.horario).all()
    
    for missa in missas:
        for vaga in missa.vagas:
            acolitos_qualificados = Usuario.query.join(Usuario.habilidades).filter(
                Habilidade.funcao == vaga.funcao,
                Usuario.is_admin == False
            ).order_by(Usuario.nome).all()
            vaga.acolitos_qualificados = acolitos_qualificados
            
    dias_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    todas_habilidades = Habilidade.query.order_by(Habilidade.funcao).all()
    return render_template('admin.html', usuarios=usuarios, missas=missas, dias_semana=dias_semana, todas_habilidades=todas_habilidades)

@app.route('/admin/usuario/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_usuario(user_id):
    usuario = Usuario.query.get_or_404(user_id)
    if usuario.is_admin:
        flash("Não é possível editar as habilidades de um administrador.", "warning")
        return redirect(url_for('admin_panel'))
    if request.method == 'POST':
        habilidades_ids = request.form.getlist('habilidades')
        usuario.habilidades.clear()
        for hab_id in habilidades_ids:
            habilidade = Habilidade.query.get(hab_id)
            if habilidade:
                usuario.habilidades.append(habilidade)
        db.session.commit()
        flash(f"Habilidades de {usuario.nome} atualizadas com sucesso!", "success")
        return redirect(url_for('admin_panel'))
    todas_habilidades = Habilidade.query.order_by(Habilidade.funcao).all()
    return render_template('edit_usuario.html', usuario=usuario, todas_habilidades=todas_habilidades)

@app.route('/admin/add_user', methods=['POST'])
@login_required
@admin_required
def add_user():
    nome, email, password = request.form.get('nome'), request.form.get('email'), request.form.get('password')
    if Usuario.query.filter_by(email=email).first():
        flash("Já existe um usuário com este email.", "danger")
    else:
        senha_hash = generate_password_hash(password)
        novo_usuario = Usuario(nome=nome, email=email, senha_hash=senha_hash, is_admin=False)
        db.session.add(novo_usuario)
        db.session.commit()
        flash(f"Acólito '{nome}' cadastrado com sucesso!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/assign_vaga/<int:vaga_id>', methods=['POST'])
@login_required
@admin_required
def assign_vaga(vaga_id):
    vaga, usuario_id = Vaga.query.get_or_404(vaga_id), request.form.get('usuario_id')
    if usuario_id:
        vaga.usuario_id = int(usuario_id)
        db.session.commit()
        flash("Acólito alocado com sucesso.", "success")
    else:
        flash("Nenhum acólito selecionado.", "warning")
    return redirect(url_for('admin_panel'))

@app.route('/admin/unassign_vaga/<int:vaga_id>', methods=['POST'])
@login_required
@admin_required
def unassign_vaga(vaga_id):
    vaga = Vaga.query.get_or_404(vaga_id)
    vaga.usuario_id = None
    db.session.commit()
    flash("Acólito removido da vaga.", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/add_missa', methods=['POST'])
@login_required
@admin_required
def add_missa():
    try:
        data_str, horario_str, funcoes = request.form.get('data'), request.form.get('horario'), request.form.getlist('funcao')
        data_obj, horario_obj = datetime.strptime(data_str, '%Y-%m-%d').date(), datetime.strptime(horario_str, '%H:%M').time()
        nova_missa = Missa(data=data_obj, horario=horario_obj)
        db.session.add(nova_missa)
        for nome_funcao in funcoes:
            if nome_funcao.strip():
                nova_vaga = Vaga(funcao=nome_funcao.strip(), missa=nova_missa)
                db.session.add(nova_vaga)
        db.session.commit()
        flash("Missa cadastrada com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao cadastrar missa: {e}", "danger")
    return redirect(url_for('admin_panel'))

# ROTAS NOVAS PARA EDITAR E EXCLUIR MISSA
@app.route('/admin/edit_missa/<int:missa_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_missa(missa_id):
    missa = Missa.query.get_or_404(missa_id)
    if request.method == 'POST':
        missa.data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        missa.horario = datetime.strptime(request.form['horario'], '%H:%M').time()
        db.session.commit()
        flash("Missa atualizada com sucesso!", "success")
        return redirect(url_for('admin_panel'))
    return render_template('edit_missa.html', missa=missa)

@app.route('/admin/delete_missa/<int:missa_id>', methods=['POST'])
@login_required
@admin_required
def delete_missa(missa_id):
    missa = Missa.query.get_or_404(missa_id)
    db.session.delete(missa)
    db.session.commit()
    flash("Missa excluída com sucesso.", "success")
    return redirect(url_for('admin_panel'))

# --- 6. ROTA DA API ---
@app.route('/api/missas')
@login_required
def get_missas():
    missas_db = Missa.query.filter_by(arquivada=False).order_by(Missa.data, Missa.horario).all()
    lista_missas = []
    dias_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    for missa in missas_db:
        slots = []
        for vaga in missa.vagas:
            slots.append({"role": vaga.funcao, "acolyte": vaga.usuario.nome if vaga.usuario else None})
        lista_missas.append({"id": missa.id, "date": missa.data.isoformat(), "day": dias_semana[missa.data.weekday()], "time": missa.horario.strftime('%H:%M'), "slots": slots})
    return jsonify({"status": "sucesso", "missas": lista_missas})

# --- 7. COMANDOS CLI ---
@app.cli.command("create-admin")
def create_admin():
    # ... (código do create-admin)
    email, password, nome = input("Digite o email: "), input("Digite a senha: "), input("Digite o nome: ")
    if Usuario.query.filter_by(email=email).first():
        print(f"Usuário '{email}' já existe.")
        return
    senha_hash = generate_password_hash(password)
    new_admin = Usuario(email=email, nome=nome, senha_hash=senha_hash, is_admin=True)
    db.session.add(new_admin); db.session.commit(); print(f"Admin '{nome}' criado.")

@app.cli.command("seed-habilidades")
def seed_habilidades():
    # ... (código do seed-habilidades)
    funcoes_padrao = ["Cerimoniário Mor (CM)", "Cerimoniário da Palavra (CP)", "Cruciferário (CR)", "Ceroferário (Vela)", "Turiferário (T)", "Naveteiro (N)", "Mitra (M)", "Báculo (B)","Acólito Geral"]
    for funcao in funcoes_padrao:
        if not Habilidade.query.filter_by(funcao=funcao).first():
            db.session.add(Habilidade(funcao=funcao)); print(f"Adicionando habilidade: {funcao}")
    db.session.commit(); print("Tabela de habilidades populada.")