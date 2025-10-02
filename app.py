import os
from flask import Flask, render_template, request, url_for, redirect, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import datetime, date, timedelta
from functools import wraps
from flask_mail import Mail, Message

load_dotenv()

# --- 1. CONFIGURAÇÃO ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key-for-dev')

# Lógica para usar o banco de dados do Render (PostgreSQL) ou SQLite local
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace("postgres://", "postgresql://", 1)
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///escala.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
}

# --- CONFIGURAÇÃO DE E-MAIL ---
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
mail = Mail(app)
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
    arquivada = db.Column(db.Boolean, default=False, nullable=False)

class Vaga(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    funcao = db.Column(db.String(100), nullable=False)
    missa_id = db.Column(db.Integer, db.ForeignKey('missa.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    usuario = db.relationship('Usuario')


# --- 3. FUNÇÕES AUXILIARES E DECORATORS ---
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


# --- 4. ROTA SECRETA PARA SETUP INICIAL ---
@app.route('/setup-inicial/<secret_key>')
def setup_database(secret_key):
    if secret_key != app.config['SECRET_KEY']:
        return "Acesso negado: chave inválida.", 403
    try:
        funcoes_padrao = ["Cerimoniário Mor (CM)", "Cerimoniário da Palavra (CP)", "Cruciferário (CR)", "Ceroferário (Vela)", "Turiferário (T)", "Naveteiro (N)", "Mitra (M)", "Báculo (B)","Acólito Geral"]
        habilidades_criadas = 0
        for funcao in funcoes_padrao:
            if not Habilidade.query.filter_by(funcao=funcao).first():
                db.session.add(Habilidade(funcao=funcao))
                habilidades_criadas += 1
        
        admin_email = os.environ.get('ADMIN_EMAIL')
        admin_pass = os.environ.get('ADMIN_PASSWORD')
        admin_nome = os.environ.get('ADMIN_NAME')
        if not (admin_email and admin_pass and admin_nome):
            return "Variáveis de ambiente do admin não configuradas.", 500

        admin_criado = "não criado (já existe)"
        if not Usuario.query.filter_by(email=admin_email).first():
            admin = Usuario(email=admin_email, nome=admin_nome, is_admin=True)
            admin.set_password(admin_pass)
            db.session.add(admin)
            admin_criado = "criado com sucesso"
        
        db.session.commit()
        return f"Setup concluído. {habilidades_criadas} habilidades criadas. Admin {admin_criado}. POR SEGURANÇA, REMOVA ESTA ROTA DO SEU CÓDIGO AGORA.", 200
    except Exception as e:
        db.session.rollback()
        return f"Ocorreu um erro durante o setup: {e}", 500


# --- 5. ROTAS DE AUTENTICAÇÃO E PÁGINAS GERAIS ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        user = Usuario.query.filter_by(email=request.form.get('email')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Email ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    # A página principal mostra a escala geral.
    return render_template('index.html')


# --- 6. ROTAS DO ACÓLITO (USUÁRIO LOGADO) ---
@app.route('/minha-escala')
@login_required
def minha_escala():
    minhas_vagas = Vaga.query.join(Missa).filter(Vaga.usuario_id == current_user.id, Missa.arquivada == False).order_by(Missa.data.asc()).all()
    return render_template('minha_escala.html', minhas_vagas=minhas_vagas)

@app.route('/pedir-substituicao/<int:vaga_id>', methods=['POST'])
@login_required
def pedir_substituicao(vaga_id):
    vaga = Vaga.query.get_or_404(vaga_id)
    if vaga.usuario_id != current_user.id:
        flash('Você não tem permissão para liberar esta vaga.', 'danger')
        return redirect(url_for('minha_escala'))

    acolito_que_saiu = current_user.nome
    missa_da_vaga = vaga.missa
    funcao_da_vaga = vaga.funcao

    vaga.usuario_id = None
    db.session.commit()
    flash('Sua vaga foi liberada com sucesso!', 'success')

    try:
        outros_acolitos = Usuario.query.filter(
            Usuario.id != current_user.id, 
            Usuario.is_admin == False
        ).all()
        if outros_acolitos:
            emails_destinatarios = [u.email for u in outros_acolitos]
            assunto = f"Oportunidade de Substituição: {funcao_da_vaga}"
            corpo_html = render_template('email/pedido_substituicao.html', 
                                         nome_acolito=acolito_que_saiu,
                                         missa=missa_da_vaga,
                                         funcao=funcao_da_vaga)
            msg = Message(subject=assunto, recipients=emails_destinatarios, html=corpo_html)
            mail.send(msg)
            flash('Os outros acólitos foram notificados sobre a vaga!', 'info')
    except Exception as e:
        flash(f'Houve um erro ao notificar o grupo: {e}', 'warning')

    return redirect(url_for('minha_escala'))


# --- 7. ROTAS DO PAINEL DO COORDENADOR (ADMIN) ---
@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    missas = Missa.query.filter_by(arquivada=False).order_by(Missa.data.desc(), Missa.horario).all()
    for missa in missas:
        for vaga in missa.vagas:
            acolitos_qualificados = Usuario.query.join(Usuario.habilidades).filter(Habilidade.funcao == vaga.funcao, Usuario.is_admin == False).order_by(Usuario.nome).all()
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
        novo_usuario = Usuario(nome=nome, email=email, is_admin=False)
        novo_usuario.set_password(password)
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
        for nome_funcao in funcoes:
            if nome_funcao.strip():
                nova_vaga = Vaga(funcao=nome_funcao.strip(), missa=nova_missa)
                db.session.add(nova_vaga)
        db.session.add(nova_missa)
        db.session.commit()
        flash("Missa cadastrada com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao cadastrar missa: {e}", "danger")
    return redirect(url_for('admin_panel'))

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

@app.route('/archive-manual', methods=['POST'])
@login_required
@admin_required
def archive_masses_manual():
    try:
        cutoff_date = date.today() - timedelta(days=15)
        num_arquivadas = db.session.query(Missa).filter(
            Missa.data < cutoff_date, 
            Missa.arquivada == False
        ).update({"arquivada": True})
        db.session.commit()
        if num_arquivadas > 0:
            flash(f'{num_arquivadas} missas antigas foram arquivadas com sucesso!', 'success')
        else:
            flash('Não há missas antigas para arquivar.', 'secondary')
    except Exception as e:
        db.session.rollback()
        flash(f'Ocorreu um erro ao arquivar as missas: {e}', 'danger')
    return redirect(url_for('admin_panel'))


# --- 8. ROTA DA API ---
@app.route('/api/missas')
@login_required
def get_missas():
    missas_db = Missa.query.filter_by(arquivada=False).order_by(Missa.data, Missa.horario).all()
    lista_missas, dias_semana = [], ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    for missa in missas_db:
        slots = []
        for vaga in missa.vagas:
            slots.append({
                "role": vaga.funcao, 
                "acolyte": vaga.usuario.nome if vaga.usuario else None,
                "vaga_id": vaga.id,
                "is_mine": (current_user.is_authenticated and vaga.usuario_id == current_user.id)
            })
        lista_missas.append({
            "id": missa.id, 
            "date": missa.data.isoformat(), 
            "day": dias_semana[missa.data.weekday()], 
            "time": missa.horario.strftime('%H:%M'), 
            "slots": slots
        })
    return jsonify({"status": "sucesso", "missas": lista_missas})


# --- 9. COMANDOS DE TERMINAL ---
@app.cli.command("create-admin")
def create_admin():
    """Cria um usuário administrador para uso local."""
    email = input("Digite o email do administrador: ")
    password = input("Digite a senha do administrador: ")
    nome = input("Digite o nome do administrador: ")
    if Usuario.query.filter_by(email=email).first():
        print(f"Usuário com o email '{email}' já existe.")
        return
    admin = Usuario(email=email, nome=nome, is_admin=True)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print(f"Administrador '{nome}' criado com sucesso!")

@app.cli.command("seed-habilidades")
def seed_habilidades():
    """Popula a tabela de habilidades com funções padrão."""
    funcoes_padrao = ["Cerimoniário Mor (CM)", "Cerimoniário da Palavra (CP)", "Cruciferário (CR)", "Ceroferário (Vela)", "Turiferário (T)", "Naveteiro (N)", "Mitra (M)", "Báculo (B)","Acólito Geral"]
    for funcao in funcoes_padrao:
        if not Habilidade.query.filter_by(funcao=funcao).first():
            db.session.add(Habilidade(funcao=funcao))
            print(f"Adicionando habilidade: {funcao}")
    db.session.commit()
    print("Tabela de habilidades populada com sucesso!")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)