import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from config import Config
from models import db, Funcionario, Categoria, Fornecedor, Produto, Cliente, Cupom, Venda, AlertaEstoque
from services import (
    AuthService,
    EstoqueService,
    CupomService,
    VendaService,
    ReportService,
    ProdutoService,
    ValidacaoService,
    PersistenciaService,
    RegraNegocioError,
    ValidacaoError,
    PersistenciaError,
)


ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    with app.app_context():
        db.create_all()

    produto_service = ProdutoService()

    def usuario_atual():
        uid = session.get("usuario_id")
        return db.session.get(Funcionario, uid) if uid else None

    @app.context_processor
    def inject_globals():
        user = usuario_atual()
        alertas_count = 0
        alertas_menu = []
        if user:
            alertas_query = AlertaEstoque.query.filter_by(resolvido=False).order_by(AlertaEstoque.data_ocorrencia.desc())
            alertas_count = alertas_query.count()
            alertas_menu = alertas_query.limit(4).all()
        return {
            "usuario_atual": user,
            "agora": datetime.now(),
            "alertas_count": alertas_count,
            "alertas_menu": alertas_menu,
        }

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not usuario_atual():
                flash("Faça login para acessar o sistema.", "warning")
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped

    def admin_required(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            user = usuario_atual()
            if not user or not user.is_admin:
                abort(403)
            return view(*args, **kwargs)
        return wrapped

    def parse_date(value):
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (TypeError, ValueError) as exc:
            raise ValidacaoError("Informe uma data válida.") from exc

    def parse_decimal(value, default="0", campo="Valor"):
        texto = str(value if value not in (None, "") else default).strip().replace(",", ".")
        try:
            numero = Decimal(texto)
        except (InvalidOperation, ValueError) as exc:
            raise ValidacaoError(f"{campo} inválido.") from exc
        if numero < 0:
            raise ValidacaoError(f"{campo} não pode ser negativo.")
        return numero

    def save_image(file):
        if not file or not file.filename:
            return None
        filename = secure_filename(file.filename)
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError("A foto deve estar no formato JPG, JPEG ou PNG.")
        unique = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{filename}"
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique))
        return unique

    @app.template_filter("brl")
    def brl(value):
        value = Decimal(str(value or 0))
        formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {formatted}"

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if usuario_atual():
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            identificador = request.form.get("identificador", "").strip()
            senha = request.form.get("senha", "")
            try:
                funcionario, erro = AuthService.autenticar(identificador, senha)
            except PersistenciaError as exc:
                flash(str(exc), "danger")
                return render_template("login.html")
            if funcionario:
                session["usuario_id"] = funcionario.id
                flash(f"Bem-vindo(a), {funcionario.nome}!", "success")
                return redirect(url_for("dashboard"))
            flash(erro, "danger")
        return render_template("login.html")

    @app.route("/cadastro", methods=["GET", "POST"])
    def cadastro_usuario():
        if usuario_atual():
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            cpf = request.form.get("cpf", "").strip()
            email = request.form.get("email", "").strip().lower()
            telefone = request.form.get("telefone", "").strip()
            cep = request.form.get("cep", "").strip()
            endereco = request.form.get("endereco", "").strip()
            data_nascimento = parse_date(request.form.get("data_nascimento"))
            senha = request.form.get("senha", "")
            confirmar_senha = request.form.get("confirmar_senha", "")

            try:
                ValidacaoService.obrigatorios(
                    nome=nome, cpf=cpf, email=email, telefone=telefone,
                    endereco=endereco, senha=senha, confirmar_senha=confirmar_senha,
                )
                ValidacaoService.cpf(cpf)
                ValidacaoService.telefone(telefone)
                ValidacaoService.email(email, obrigatorio=True)
                ValidacaoService.cep(cep, obrigatorio=False)
            except ValidacaoError as exc:
                flash(str(exc), "danger")
                return render_template("cadastro_usuario.html")

            if senha != confirmar_senha:
                flash("As senhas não coincidem.", "danger")
                return render_template("cadastro_usuario.html")

            if Funcionario.query.filter((Funcionario.cpf == cpf) | (Funcionario.email == email)).first():
                flash("Já existe um usuário com este CPF ou e-mail.", "danger")
                return render_template("cadastro_usuario.html")

            if not AuthService.senha_forte(senha):
                flash("A senha deve ter 8+ caracteres, letra maiúscula, número e caractere especial.", "danger")
                return render_template("cadastro_usuario.html")

            item = Funcionario(
                cpf=cpf,
                nome=nome,
                email=email,
                telefone=telefone,
                cep=cep,
                endereco=endereco,
                data_nascimento=data_nascimento,
                cargo="Funcionário",
                salario=Decimal("0.00"),
                horario_trabalho="",
                perfil="funcionario",
                ativo=True,
            )
            item.set_senha(senha)
            db.session.add(item)
            try:
                PersistenciaService.confirmar("Não foi possível concluir o cadastro. Tente novamente.")
            except PersistenciaError as exc:
                flash(str(exc), "danger")
                return render_template("cadastro_usuario.html")

            flash("Cadastro realizado com sucesso. Agora você já pode entrar.", "success")
            return redirect(url_for("login"))

        return render_template("cadastro_usuario.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Sessão encerrada.", "info")
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def dashboard():
        indicadores = ReportService.indicadores()
        ultimas_vendas = Venda.query.order_by(Venda.data_venda.desc()).limit(5).all()
        alertas = AlertaEstoque.query.filter_by(resolvido=False).order_by(AlertaEstoque.data_ocorrencia.desc()).limit(5).all()
        return render_template("dashboard.html", indicadores=indicadores, ultimas_vendas=ultimas_vendas, alertas=alertas)

    # FUNCIONÁRIOS
    @app.route("/funcionarios")
    @admin_required
    def funcionarios():
        return render_template("funcionarios.html", funcionarios=Funcionario.query.order_by(Funcionario.nome).all())

    @app.route("/funcionarios/novo", methods=["GET", "POST"])
    @admin_required
    def funcionario_novo():
        if request.method == "POST":
            cpf = request.form.get("cpf", "").strip()
            email = request.form.get("email", "").strip().lower()
            senha = request.form.get("senha", "")
            nome = request.form.get("nome", "").strip()
            telefone = request.form.get("telefone", "").strip()
            endereco = request.form.get("endereco", "").strip()
            cargo = request.form.get("cargo", "").strip()
            try:
                ValidacaoService.obrigatorios(
                    nome=nome, cpf=cpf, email=email, telefone=telefone,
                    endereco=endereco, cargo=cargo, senha=senha,
                )
                ValidacaoService.cpf(cpf)
                ValidacaoService.telefone(telefone)
                ValidacaoService.email(email, obrigatorio=True)
                ValidacaoService.cep(request.form.get("cep", "").strip(), obrigatorio=False)
            except ValidacaoError as exc:
                flash(str(exc), "danger")
                return render_template("funcionario_form.html", item=None)
            if Funcionario.query.filter((Funcionario.cpf == cpf) | (Funcionario.email == email)).first():
                flash("Já existe um funcionário com este CPF ou e-mail.", "danger")
                return render_template("funcionario_form.html", item=None)
            if not AuthService.senha_forte(senha):
                flash("A senha deve ter 8+ caracteres, letra maiúscula, número e caractere especial.", "danger")
                return render_template("funcionario_form.html", item=None)
            try:
                foto = save_image(request.files.get("foto"))
                item = Funcionario(
                    cpf=cpf,
                    nome=nome,
                    email=email,
                    telefone=telefone,
                    cep=request.form.get("cep", "").strip(),
                    endereco=endereco,
                    data_nascimento=parse_date(request.form.get("data_nascimento")),
                    cargo=cargo,
                    salario=parse_decimal(request.form.get("salario"), campo="Salário"),
                    horario_trabalho=request.form.get("horario_trabalho", "").strip(),
                    perfil=request.form.get("perfil", "funcionario"),
                    foto=foto,
                )
                item.set_senha(senha)
                db.session.add(item)
                PersistenciaService.confirmar()
                flash("Funcionário cadastrado com sucesso.", "success")
                return redirect(url_for("funcionarios"))
            except ValueError as exc:
                flash(str(exc), "danger")
        return render_template("funcionario_form.html", item=None)

    @app.route("/funcionarios/<int:item_id>/editar", methods=["GET", "POST"])
    @admin_required
    def funcionario_editar(item_id):
        item = db.get_or_404(Funcionario, item_id)
        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            telefone = request.form.get("telefone", "").strip()
            cep = request.form.get("cep", "").strip()
            endereco = request.form.get("endereco", "").strip()
            cargo = request.form.get("cargo", "").strip()
            try:
                ValidacaoService.obrigatorios(
                    nome=nome, telefone=telefone, endereco=endereco, cargo=cargo
                )
                ValidacaoService.telefone(telefone)
                ValidacaoService.cep(cep, obrigatorio=False)
            except ValidacaoError as exc:
                flash(str(exc), "danger")
                return render_template("funcionario_form.html", item=item)
            item.nome = nome
            item.telefone = telefone
            item.cep = cep
            item.endereco = endereco
            item.data_nascimento = parse_date(request.form.get("data_nascimento"))
            item.cargo = cargo
            item.salario = parse_decimal(request.form.get("salario"), campo="Salário")
            item.horario_trabalho = request.form.get("horario_trabalho", "").strip()
            item.perfil = request.form.get("perfil", item.perfil)
            item.ativo = request.form.get("ativo") == "1"
            nova_senha = request.form.get("senha", "")
            if nova_senha:
                if not AuthService.senha_forte(nova_senha):
                    flash("A nova senha não atende aos requisitos de segurança.", "danger")
                    return render_template("funcionario_form.html", item=item)
                item.set_senha(nova_senha)
            try:
                nova_foto = save_image(request.files.get("foto"))
                if nova_foto:
                    item.foto = nova_foto
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("funcionario_form.html", item=item)
            PersistenciaService.confirmar()
            flash("Funcionário atualizado.", "success")
            return redirect(url_for("funcionarios"))
        return render_template("funcionario_form.html", item=item)

    @app.route("/funcionarios/<int:item_id>/excluir", methods=["POST"])
    @admin_required
    def funcionario_excluir(item_id):
        item = db.get_or_404(Funcionario, item_id)
        if item.id == usuario_atual().id:
            flash("Você não pode excluir o próprio usuário logado.", "danger")
        elif item.vendas:
            item.ativo = False
            PersistenciaService.confirmar()
            flash("O funcionário possui vendas e foi inativado para preservar o histórico.", "warning")
        else:
            db.session.delete(item)
            PersistenciaService.confirmar()
            flash("Funcionário excluído.", "success")
        return redirect(url_for("funcionarios"))

    # CATEGORIAS
    @app.route("/categorias", methods=["GET", "POST"])
    @login_required
    def categorias():
        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            if nome and not Categoria.query.filter_by(nome=nome).first():
                db.session.add(Categoria(nome=nome))
                PersistenciaService.confirmar()
                flash("Categoria cadastrada.", "success")
            else:
                flash("Informe um nome novo para a categoria.", "warning")
        return render_template("categorias.html", categorias=Categoria.query.order_by(Categoria.nome).all())

    @app.route("/categorias/<int:item_id>/excluir", methods=["POST"])
    @login_required
    def categoria_excluir(item_id):
        item = db.get_or_404(Categoria, item_id)
        if item.produtos:
            flash("Não é possível excluir categoria que possui produtos.", "danger")
        else:
            db.session.delete(item)
            PersistenciaService.confirmar()
            flash("Categoria excluída.", "success")
        return redirect(url_for("categorias"))

    # FORNECEDORES
    @app.route("/fornecedores")
    @login_required
    def fornecedores():
        return render_template("fornecedores.html", fornecedores=Fornecedor.query.order_by(Fornecedor.nome_empresa).all())

    @app.route("/fornecedores/novo", methods=["GET", "POST"])
    @login_required
    def fornecedor_novo():
        if request.method == "POST":
            nome_empresa = request.form.get("nome_empresa", "").strip()
            representante = request.form.get("representante", "").strip()
            telefone = request.form.get("telefone", "").strip()
            email = request.form.get("email", "").strip().lower()
            cep = request.form.get("cep", "").strip()
            endereco = request.form.get("endereco", "").strip()
            try:
                ValidacaoService.obrigatorios(
                    empresa=nome_empresa, representante=representante, telefone=telefone
                )
                ValidacaoService.telefone(telefone)
                ValidacaoService.email(email, obrigatorio=False)
                ValidacaoService.cep(cep, obrigatorio=False)
            except ValidacaoError as exc:
                flash(str(exc), "danger")
                return render_template("fornecedor_form.html", item=None)
            item = Fornecedor(
                nome_empresa=nome_empresa,
                representante=representante,
                telefone=telefone,
                email=email,
                cep=cep,
                endereco=endereco,
            )
            db.session.add(item)
            PersistenciaService.confirmar()
            flash("Fornecedor cadastrado.", "success")
            return redirect(url_for("fornecedores"))
        return render_template("fornecedor_form.html", item=None)

    @app.route("/fornecedores/<int:item_id>/editar", methods=["GET", "POST"])
    @login_required
    def fornecedor_editar(item_id):
        item = db.get_or_404(Fornecedor, item_id)
        if request.method == "POST":
            valores = {
                field: request.form.get(field, "").strip()
                for field in ["nome_empresa", "representante", "telefone", "email", "cep", "endereco"]
            }
            try:
                ValidacaoService.obrigatorios(
                    empresa=valores["nome_empresa"],
                    representante=valores["representante"],
                    telefone=valores["telefone"],
                )
                ValidacaoService.telefone(valores["telefone"])
                ValidacaoService.email(valores["email"], obrigatorio=False)
                ValidacaoService.cep(valores["cep"], obrigatorio=False)
            except ValidacaoError as exc:
                flash(str(exc), "danger")
                return render_template("fornecedor_form.html", item=item)
            for field, valor in valores.items():
                setattr(item, field, valor)
            PersistenciaService.confirmar()
            flash("Fornecedor atualizado.", "success")
            return redirect(url_for("fornecedores"))
        return render_template("fornecedor_form.html", item=item)

    @app.route("/fornecedores/<int:item_id>/excluir", methods=["POST"])
    @login_required
    def fornecedor_excluir(item_id):
        item = db.get_or_404(Fornecedor, item_id)
        if item.produtos:
            flash("Não é possível excluir fornecedor com produtos relacionados.", "danger")
        else:
            db.session.delete(item)
            PersistenciaService.confirmar()
            flash("Fornecedor excluído.", "success")
        return redirect(url_for("fornecedores"))

    # CLIENTES
    @app.route("/clientes")
    @login_required
    def clientes():
        termo = request.args.get("q", "").strip()
        query = Cliente.query
        if termo:
            query = query.filter((Cliente.nome.ilike(f"%{termo}%")) | (Cliente.cpf.ilike(f"%{termo}%")))
        return render_template("clientes.html", clientes=query.order_by(Cliente.nome).all(), termo=termo)

    @app.route("/clientes/novo", methods=["GET", "POST"])
    @login_required
    def cliente_novo():
        if request.method == "POST":
            cpf = request.form.get("cpf", "").strip()
            nome = request.form.get("nome", "").strip()
            telefone = request.form.get("telefone", "").strip()
            email = request.form.get("email", "").strip().lower()
            cep = request.form.get("cep", "").strip()
            endereco = request.form.get("endereco", "").strip()
            try:
                ValidacaoService.obrigatorios(nome=nome, cpf=cpf, telefone=telefone)
                ValidacaoService.cpf(cpf)
                ValidacaoService.telefone(telefone)
                ValidacaoService.email(email, obrigatorio=False)
                ValidacaoService.cep(cep, obrigatorio=False)
            except ValidacaoError as exc:
                flash(str(exc), "danger")
                return render_template("cliente_form.html", item=None)
            if Cliente.query.filter_by(cpf=cpf).first():
                flash("Já existe um cliente com este CPF.", "danger")
                return render_template("cliente_form.html", item=None)
            item = Cliente(
                cpf=cpf,
                nome=nome,
                telefone=telefone,
                email=email,
                data_nascimento=parse_date(request.form.get("data_nascimento")),
                cep=cep,
                endereco=endereco,
            )
            db.session.add(item)
            PersistenciaService.confirmar()
            flash("Cliente cadastrado.", "success")
            return redirect(url_for("clientes"))
        return render_template("cliente_form.html", item=None)

    @app.route("/clientes/<int:item_id>")
    @login_required
    def cliente_detalhe(item_id):
        item = db.get_or_404(Cliente, item_id)
        vendas_cliente = Venda.query.filter_by(cliente_id=item.id).order_by(Venda.data_venda.desc()).all()
        cupom_ativo = CupomService.cupom_ativo(item)
        total_gasto = sum((Decimal(str(v.valor_total)) for v in vendas_cliente), Decimal("0.00"))
        return render_template("cliente_detalhe.html", item=item, vendas=vendas_cliente, cupom_ativo=cupom_ativo, total_gasto=total_gasto)

    @app.route("/clientes/<int:item_id>/editar", methods=["GET", "POST"])
    @login_required
    def cliente_editar(item_id):
        item = db.get_or_404(Cliente, item_id)
        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            telefone = request.form.get("telefone", "").strip()
            email = request.form.get("email", "").strip().lower()
            cep = request.form.get("cep", "").strip()
            endereco = request.form.get("endereco", "").strip()
            try:
                ValidacaoService.obrigatorios(nome=nome, telefone=telefone)
                ValidacaoService.telefone(telefone)
                ValidacaoService.email(email, obrigatorio=False)
                ValidacaoService.cep(cep, obrigatorio=False)
            except ValidacaoError as exc:
                flash(str(exc), "danger")
                return render_template("cliente_form.html", item=item)
            item.nome = nome
            item.telefone = telefone
            item.email = email
            item.data_nascimento = parse_date(request.form.get("data_nascimento"))
            item.cep = cep
            item.endereco = endereco
            PersistenciaService.confirmar()
            flash("Cliente atualizado.", "success")
            return redirect(url_for("clientes"))
        return render_template("cliente_form.html", item=item)

    @app.route("/clientes/<int:item_id>/excluir", methods=["POST"])
    @login_required
    def cliente_excluir(item_id):
        item = db.get_or_404(Cliente, item_id)
        if item.vendas:
            flash("Não é possível excluir cliente com histórico de vendas.", "danger")
        else:
            db.session.delete(item)
            PersistenciaService.confirmar()
            flash("Cliente excluído.", "success")
        return redirect(url_for("clientes"))

    # PRODUTOS
    @app.route("/produtos")
    @login_required
    def produtos():
        categoria_id = request.args.get("categoria_id", type=int)
        termo = request.args.get("q", "").strip()
        if termo and not categoria_id:
            produtos_encontrados = produto_service.buscar(termo)
        else:
            query = Produto.query
            if categoria_id:
                query = query.filter_by(categoria_id=categoria_id)
            if termo:
                query = query.filter(
                    (Produto.nome.ilike(f"%{termo}%"))
                    | (Produto.codigo_barras.ilike(f"%{termo}%"))
                )
            produtos_encontrados = query.order_by(Produto.nome).all()
        return render_template(
            "produtos.html",
            produtos=produtos_encontrados,
            categorias=Categoria.query.order_by(Categoria.nome).all(),
            categoria_id=categoria_id,
            termo=termo,
        )

    @app.route("/produtos/novo", methods=["GET", "POST"])
    @login_required
    def produto_novo():
        categorias_list = Categoria.query.order_by(Categoria.nome).all()
        fornecedores_list = Fornecedor.query.order_by(Fornecedor.nome_empresa).all()
        if request.method == "POST":
            codigo = request.form.get("codigo_barras", "").strip()
            nome = request.form.get("nome", "").strip()
            categoria_id = request.form.get("categoria_id", type=int)
            fornecedor_id = request.form.get("fornecedor_id", type=int)
            try:
                ValidacaoService.obrigatorios(
                    codigo_de_barras=codigo, nome=nome,
                    categoria=categoria_id, fornecedor=fornecedor_id,
                )
                valor_venda = parse_decimal(request.form.get("valor_venda"), campo="Valor de venda")
                valor_custo = parse_decimal(request.form.get("valor_custo"), campo="Valor de custo")
                estoque = request.form.get("estoque", type=int)
                minimo = request.form.get("quantidade_minima", type=int)
                if estoque is None or minimo is None:
                    raise ValidacaoError("Estoque e quantidade mínima devem ser números inteiros.")
                ValidacaoService.nao_negativo(estoque, "Estoque")
                ValidacaoService.nao_negativo(minimo, "Quantidade mínima")
                if not db.session.get(Categoria, categoria_id):
                    raise ValidacaoError("Categoria selecionada não existe.")
                if not db.session.get(Fornecedor, fornecedor_id):
                    raise ValidacaoError("Fornecedor selecionado não existe.")
            except ValidacaoError as exc:
                flash(str(exc), "danger")
                return render_template("produto_form.html", item=None, categorias=categorias_list, fornecedores=fornecedores_list)
            if Produto.query.filter_by(codigo_barras=codigo).first():
                flash("Já existe um produto com este código de barras.", "danger")
                return render_template("produto_form.html", item=None, categorias=categorias_list, fornecedores=fornecedores_list)
            try:
                foto = save_image(request.files.get("foto"))
                item = Produto(
                    codigo_barras=codigo,
                    nome=nome,
                    valor_venda=valor_venda,
                    valor_custo=valor_custo,
                    descricao=request.form.get("descricao", "").strip(),
                    estoque=estoque,
                    quantidade_minima=minimo,
                    categoria_id=categoria_id,
                    fornecedor_id=fornecedor_id,
                    foto=foto,
                )
                db.session.add(item)
                db.session.flush()
                EstoqueService.verificar_alerta(item)
                PersistenciaService.confirmar()
                flash("Produto cadastrado.", "success")
                return redirect(url_for("produtos"))
            except ValueError as exc:
                flash(str(exc), "danger")
        return render_template("produto_form.html", item=None, categorias=categorias_list, fornecedores=fornecedores_list)

    @app.route("/produtos/<int:item_id>/editar", methods=["GET", "POST"])
    @login_required
    def produto_editar(item_id):
        item = db.get_or_404(Produto, item_id)
        categorias_list = Categoria.query.order_by(Categoria.nome).all()
        fornecedores_list = Fornecedor.query.order_by(Fornecedor.nome_empresa).all()
        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            categoria_id = request.form.get("categoria_id", type=int)
            fornecedor_id = request.form.get("fornecedor_id", type=int)
            estoque = request.form.get("estoque", type=int)
            minimo = request.form.get("quantidade_minima", type=int)
            try:
                ValidacaoService.obrigatorios(
                    nome=nome, categoria=categoria_id, fornecedor=fornecedor_id
                )
                valor_venda = parse_decimal(request.form.get("valor_venda"), campo="Valor de venda")
                valor_custo = parse_decimal(request.form.get("valor_custo"), campo="Valor de custo")
                if estoque is None or minimo is None:
                    raise ValidacaoError("Estoque e quantidade mínima devem ser números inteiros.")
                ValidacaoService.nao_negativo(estoque, "Estoque")
                ValidacaoService.nao_negativo(minimo, "Quantidade mínima")
                if not db.session.get(Categoria, categoria_id):
                    raise ValidacaoError("Categoria selecionada não existe.")
                if not db.session.get(Fornecedor, fornecedor_id):
                    raise ValidacaoError("Fornecedor selecionado não existe.")
            except ValidacaoError as exc:
                flash(str(exc), "danger")
                return render_template("produto_form.html", item=item, categorias=categorias_list, fornecedores=fornecedores_list)
            item.nome = nome
            item.valor_venda = valor_venda
            item.valor_custo = valor_custo
            item.descricao = request.form.get("descricao", "").strip()
            item.estoque = estoque
            item.quantidade_minima = minimo
            item.categoria_id = categoria_id
            item.fornecedor_id = fornecedor_id
            try:
                nova_foto = save_image(request.files.get("foto"))
                if nova_foto:
                    item.foto = nova_foto
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("produto_form.html", item=item, categorias=categorias_list, fornecedores=fornecedores_list)
            EstoqueService.verificar_alerta(item)
            PersistenciaService.confirmar()
            flash("Produto atualizado.", "success")
            return redirect(url_for("produtos"))
        return render_template("produto_form.html", item=item, categorias=categorias_list, fornecedores=fornecedores_list)

    @app.route("/produtos/<int:item_id>/excluir", methods=["POST"])
    @login_required
    def produto_excluir(item_id):
        item = db.get_or_404(Produto, item_id)
        if item.itens_venda:
            flash("Não é possível excluir produto que já aparece em vendas.", "danger")
        else:
            db.session.delete(item)
            PersistenciaService.confirmar()
            flash("Produto excluído.", "success")
        return redirect(url_for("produtos"))

    # CARRINHO E VENDAS
    def get_cart_dict():
        return session.setdefault("carrinho", {})

    def build_cart():
        cart = get_cart_dict()
        items = []
        for pid, qty in cart.items():
            produto = db.session.get(Produto, int(pid))
            if produto:
                items.append({"produto": produto, "quantidade": int(qty), "subtotal": Decimal(str(produto.valor_venda)) * int(qty)})
        return items

    @app.route("/carrinho", methods=["GET", "POST"])
    @login_required
    def carrinho():
        if request.method == "POST":
            produto_id = request.form.get("produto_id", type=int)
            quantidade = request.form.get("quantidade", type=int)
            if not produto_id:
                flash("Selecione um produto.", "danger")
                return redirect(url_for("carrinho"))
            produto = produto_service.buscar(produto_id)
            if produto is None:
                abort(404)
            if quantidade is None:
                flash("Informe uma quantidade válida.", "danger")
                return redirect(url_for("carrinho"))
            cart = get_cart_dict()
            atual = int(cart.get(str(produto_id), 0))
            if quantidade <= 0:
                flash("A quantidade deve ser maior que zero.", "warning")
            elif atual + quantidade > produto.estoque:
                flash(f"Não foi possível adicionar {produto.nome}: estoque disponível = {produto.estoque}.", "danger")
            else:
                cart[str(produto_id)] = atual + quantidade
                session.modified = True
                flash("Produto adicionado ao carrinho.", "success")
            return redirect(url_for("carrinho"))
        items = build_cart()
        total = sum((item["subtotal"] for item in items), Decimal("0.00"))
        return render_template("carrinho.html", items=items, total=total, produtos=Produto.query.order_by(Produto.nome).all(), clientes=Cliente.query.order_by(Cliente.nome).all())

    @app.route("/carrinho/<int:produto_id>/remover", methods=["POST"])
    @login_required
    def carrinho_remover(produto_id):
        cart = get_cart_dict()
        cart.pop(str(produto_id), None)
        session.modified = True
        return redirect(url_for("carrinho"))

    @app.route("/carrinho/limpar", methods=["POST"])
    @login_required
    def carrinho_limpar():
        session["carrinho"] = {}
        return redirect(url_for("carrinho"))

    @app.route("/vendas/finalizar", methods=["POST"])
    @login_required
    def venda_finalizar():
        cliente_id = request.form.get("cliente_id", type=int)
        if not cliente_id:
            flash("Selecione um cliente antes de finalizar a venda.", "danger")
            return redirect(url_for("carrinho"))
        cliente = db.session.get(Cliente, cliente_id)
        if cliente is None:
            flash("O cliente selecionado não foi encontrado.", "danger")
            return redirect(url_for("carrinho"))
        cupom = None
        cupom_id = request.form.get("cupom_id", type=int)
        if cupom_id:
            cupom = db.get_or_404(Cupom, cupom_id)
            if cupom.cliente_id != cliente.id or cupom.utilizado:
                flash("Cupom inválido para este cliente.", "danger")
                return redirect(url_for("carrinho"))
        try:
            venda = VendaService.finalizar(cliente, usuario_atual(), build_cart(), cupom)
            session["carrinho"] = {}
            flash(f"Venda #{venda.id} concluída com sucesso.", "success")
            return redirect(url_for("vendas"))
        except (RegraNegocioError, ValidacaoError, PersistenciaError) as exc:
            flash(str(exc), "danger")
            return redirect(url_for("carrinho"))

    @app.route("/api/clientes/<int:cliente_id>/cupons")
    @login_required
    def api_cupons_cliente(cliente_id):
        cliente = db.get_or_404(Cliente, cliente_id)
        cupom = CupomService.cupom_ativo(cliente)
        if not cupom:
            return {"cupons": []}
        return {"cupons": [{"id": cupom.id, "codigo": cupom.codigo, "desconto": cupom.desconto}]}

    @app.route("/vendas")
    @login_required
    def vendas():
        return render_template("vendas.html", vendas=Venda.query.order_by(Venda.data_venda.desc()).all())

    @app.route("/vendas/<int:item_id>")
    @login_required
    def venda_detalhe(item_id):
        item = db.get_or_404(Venda, item_id)
        return render_template("venda_detalhe.html", item=item)

    # CUPONS
    @app.route("/cupons")
    @login_required
    def cupons():
        return render_template("cupons.html", cupons=Cupom.query.order_by(Cupom.criado_em.desc()).all())

    # ALERTAS
    @app.route("/alertas")
    @login_required
    def alertas():
        return render_template("alertas.html", alertas=AlertaEstoque.query.order_by(AlertaEstoque.resolvido, AlertaEstoque.data_ocorrencia.desc()).all())

    @app.route("/alertas/<int:item_id>/resolver", methods=["POST"])
    @login_required
    def alerta_resolver(item_id):
        item = db.get_or_404(AlertaEstoque, item_id)
        item.resolvido = True
        PersistenciaService.confirmar()
        flash("Alerta marcado como resolvido.", "success")
        return redirect(url_for("alertas"))

    # RELATÓRIOS
    @app.route("/relatorios")
    @admin_required
    def relatorios():
        dados = {
            "indicadores": ReportService.indicadores(),
            "produtos": ReportService.produtos_mais_vendidos(),
            "clientes": ReportService.clientes_que_mais_compram(),
            "fornecedores": ReportService.fornecedores_com_mais_produtos(),
            "funcionarios": ReportService.desempenho_funcionarios(),
        }
        return render_template("relatorios.html", **dados)

    @app.route("/relatorios/imprimir")
    @admin_required
    def relatorio_imprimir():
        secoes = request.args.getlist("secao") or ["indicadores", "produtos", "clientes", "fornecedores", "funcionarios"]
        dados = {
            "secoes": secoes,
            "indicadores": ReportService.indicadores(),
            "produtos": ReportService.produtos_mais_vendidos(),
            "clientes": ReportService.clientes_que_mais_compram(),
            "fornecedores": ReportService.fornecedores_com_mais_produtos(),
            "funcionarios": ReportService.desempenho_funcionarios(),
        }
        return render_template("relatorio_print.html", **dados)

    @app.errorhandler(403)
    def forbidden(_):
        return render_template(
            "erro.html",
            codigo=403,
            mensagem="Operação não permitida para este usuário.",
        ), 403

    @app.errorhandler(404)
    def not_found(_):
        return render_template(
            "erro.html",
            codigo=404,
            mensagem="Página ou registro não encontrado.",
        ), 404

    @app.errorhandler(ValidacaoError)
    def validation_error(exc):
        db.session.rollback()
        return render_template(
            "erro.html",
            codigo=400,
            mensagem=str(exc),
        ), 400

    @app.errorhandler(RegraNegocioError)
    def business_error(exc):
        db.session.rollback()
        return render_template(
            "erro.html",
            codigo=409,
            mensagem=str(exc),
        ), 409

    @app.errorhandler(PersistenciaError)
    def persistence_error(exc):
        db.session.rollback()
        app.logger.error("Falha de persistência: %s", exc)
        return render_template(
            "erro.html",
            codigo=500,
            mensagem=str(exc),
        ), 500

    @app.errorhandler(SQLAlchemyError)
    def database_error(exc):
        db.session.rollback()
        app.logger.error("Falha de banco de dados: %s", exc)
        return render_template(
            "erro.html",
            codigo=500,
            mensagem=(
                "Não foi possível carregar ou salvar os dados neste momento. "
                "Tente novamente."
            ),
        ), 500

    @app.errorhandler(500)
    def internal_error(exc):
        db.session.rollback()
        app.logger.error("Erro interno: %s", exc)
        return render_template(
            "erro.html",
            codigo=500,
            mensagem="Não foi possível concluir a operação. Tente novamente.",
        ), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
